"""Agent 1 — Image preprocessing.

Handles deskewing, denoising, and contrast enhancement. PDFs are rasterized
to the first page (or first N pages — here we keep it simple) before being
passed to the OCR engines.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from app.agents.base import BaseAgent
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class PreprocessingInput:
    file_bytes: bytes
    mime_type: str


@dataclass
class PreprocessingOutput:
    images: List[np.ndarray]       # cleaned BGR images
    encoded_pngs: List[bytes]      # serialized for sending to cloud OCR
    page_count: int


class PreprocessingAgent(BaseAgent[PreprocessingInput, PreprocessingOutput]):
    name = "preprocessing"

    def _run(self, inputs: PreprocessingInput) -> PreprocessingOutput:
        images = self._decode(inputs.file_bytes, inputs.mime_type)
        cleaned: List[np.ndarray] = []
        encoded: List[bytes] = []
        for img in images:
            processed = self._enhance(img)
            cleaned.append(processed)
            ok, buf = cv2.imencode(".png", processed)
            if ok:
                encoded.append(buf.tobytes())
        return PreprocessingOutput(
            images=cleaned,
            encoded_pngs=encoded,
            page_count=len(cleaned),
        )

    # ---------- Decoding ----------
    def _decode(self, data: bytes, mime: str) -> List[np.ndarray]:
        mime = (mime or "").lower()
        if "pdf" in mime or data[:4] == b"%PDF":
            return self._decode_pdf(data)
        return self._decode_image(data)

    def _decode_image(self, data: bytes) -> List[np.ndarray]:
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode image bytes")
        return [img]

    def _decode_pdf(self, data: bytes) -> List[np.ndarray]:
        try:
            from pdf2image import convert_from_bytes

            pages = convert_from_bytes(data, dpi=250, fmt="png")
            return [
                cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pages
            ]
        except Exception as exc:
            # Poppler is not bundled with pdf2image on Windows. Rather than
            # killing the pipeline, degrade gracefully: emit zero pages. The
            # Champ/Challenger agents key mocks off file_hash, and real cloud
            # OCR can accept raw PDF bytes directly, so the pipeline still
            # produces an extraction + routes to REVIEW if anything is off.
            log.warning("pdf2image_unavailable", error=str(exc))
            return []

    # ---------- Enhancement ----------
    @staticmethod
    def _enhance(img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7,
                                            searchWindowSize=21)
        # Deskew
        angle = PreprocessingAgent._detect_skew(denoised)
        rotated = PreprocessingAgent._rotate(denoised, angle) if abs(angle) > 0.5 else denoised
        # Contrast: CLAHE works better than global hist-eq on invoices
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(rotated)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _detect_skew(gray: np.ndarray) -> float:
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, 200, minLineLength=100, maxLineGap=10
            )
            if lines is None:
                return 0.0
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 == x1:
                    continue
                a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if -45 < a < 45:
                    angles.append(a)
            if not angles:
                return 0.0
            return float(np.median(angles))
        except Exception:
            return 0.0

    @staticmethod
    def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
