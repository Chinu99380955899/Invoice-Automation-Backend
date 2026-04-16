"""Agent 3 — Challenger OCR: PaddleOCR.

Runs independently from Champ. Field extraction from raw OCR lines is a
heuristic: vendor = first non-empty line, invoice number & total identified
by regex. The goal is NOT to match Champ perfectly but to provide an
independent signal for the validation agent to compare against.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from app.agents.base import BaseAgent
from app.agents.champ_ocr import _mock_extract
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceExtracted, InvoiceItemCreate

log = get_logger(__name__)

_INV_NUM_RE = re.compile(r"(?:invoice|inv)[#:\s\-]*([A-Z0-9\-]{4,})", re.I)
_PO_RE = re.compile(r"(?:p\.?o\.?|purchase\s*order)[#:\s\-]*([A-Z0-9\-]{3,})", re.I)
_TOTAL_RE = re.compile(r"total[\s:]*\$?([\d,]+\.\d{2})", re.I)
_SUBTOTAL_RE = re.compile(r"sub[\s-]?total[\s:]*\$?([\d,]+\.\d{2})", re.I)
_TAX_RE = re.compile(r"\btax[\s:]*\$?([\d,]+\.\d{2})", re.I)
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%b-%Y", "%B %d, %Y")


@dataclass
class ChallengerOCRInput:
    encoded_pngs: List[bytes]  # from preprocessing
    file_hash: str


class ChallengerOCRAgent(BaseAgent[ChallengerOCRInput, InvoiceExtracted]):
    name = "challenger_ocr_paddle"

    def _run(self, inputs: ChallengerOCRInput) -> InvoiceExtracted:
        if settings.use_mock_paddle_ocr:
            return _mock_extract(inputs.file_hash, engine="challenger")
        return self._real_extract(inputs)

    def _real_extract(self, inputs: ChallengerOCRInput) -> InvoiceExtracted:
        from paddleocr import PaddleOCR  # heavy import — keep lazy
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang=settings.paddle_ocr_lang,
            use_gpu=settings.paddle_ocr_use_gpu,
            show_log=False,
        )
        lines: List[tuple[str, float]] = []
        for png in inputs.encoded_pngs:
            try:
                result = ocr.ocr(png, cls=True)
                for block in result or []:
                    for item in block or []:
                        text = item[1][0] if len(item[1]) else ""
                        conf = float(item[1][1]) if len(item[1]) > 1 else 0.0
                        if text:
                            lines.append((text, conf))
            except Exception as exc:
                log.warning("paddle_page_failed", error=str(exc))
                continue

        return self._parse_lines(lines)

    # ---------- Parsing ----------
    @staticmethod
    def _parse_lines(lines: List[tuple[str, float]]) -> InvoiceExtracted:
        full_text = "\n".join(t for t, _ in lines)
        confidences = [c for _, c in lines if c > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        vendor = next(
            (t for t, _ in lines if len(t) > 2 and not t[0].isdigit()), None
        )
        number = _first_match(_INV_NUM_RE, full_text)
        po = _first_match(_PO_RE, full_text)
        total = _parse_decimal(_first_match(_TOTAL_RE, full_text))
        subtotal = _parse_decimal(_first_match(_SUBTOTAL_RE, full_text))
        tax = _parse_decimal(_first_match(_TAX_RE, full_text))
        inv_date = _parse_date(full_text)

        return InvoiceExtracted(
            vendor_name=vendor,
            invoice_number=number,
            invoice_date=inv_date,
            currency="USD",
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            purchase_order=po,
            items=[],  # Paddle line-item extraction is noisy; leave empty here.
            confidence_scores={
                "vendor_name": avg_conf,
                "invoice_number": avg_conf,
                "total_amount": avg_conf,
                "subtotal": avg_conf,
                "tax_amount": avg_conf,
            },
            raw={"engine": "paddle_ocr", "line_count": len(lines)},
        )


# ------- parse helpers -------
def _first_match(regex: re.Pattern, text: str) -> Optional[str]:
    m = regex.search(text)
    return m.group(1).strip() if m else None


def _parse_decimal(s: Optional[str]) -> Optional[Decimal]:
    if not s:
        return None
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def _parse_date(text: str) -> Optional[date]:
    # Try several common formats — first hit wins
    date_token = re.search(
        r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
        r"\d{1,2}-[A-Za-z]{3}-\d{2,4}|[A-Za-z]+\s\d{1,2},\s\d{4})\b",
        text,
    )
    if not date_token:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_token.group(1), fmt).date()
        except ValueError:
            continue
    return None
