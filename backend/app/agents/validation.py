"""Agent 4 — Validation engine.

Compares Champ vs Challenger outputs, applies business rules, and decides
between AUTO_APPROVED and REVIEW_REQUIRED.

Business rules:
  1. If either engine is missing, fall back to the other and flag REVIEW.
  2. total ≈ sum(line_items) + tax  (within tolerance).
  3. Field-level agreement ratio must meet threshold.
  4. Weighted average confidence must meet threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import BaseAgent
from app.core.config import settings
from app.db.models.invoice import InvoiceStatus
from app.schemas.invoice import InvoiceExtracted

_COMPARED_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "total_amount",
    "subtotal",
    "tax_amount",
    "purchase_order",
)


@dataclass
class ValidationInput:
    champ: Optional[InvoiceExtracted]
    challenger: Optional[InvoiceExtracted]


@dataclass
class ValidationOutput:
    decision: InvoiceStatus
    merged: InvoiceExtracted
    confidence_score: float
    report: Dict[str, Any] = field(default_factory=dict)


class ValidationAgent(BaseAgent[ValidationInput, ValidationOutput]):
    name = "validation"

    def _run(self, inputs: ValidationInput) -> ValidationOutput:
        champ, chall = inputs.champ, inputs.challenger

        # --- Degradation paths ---
        if champ is None and chall is None:
            raise RuntimeError("Both OCR engines failed — cannot validate")
        if champ is None:
            return _review(chall, reason="Champ OCR unavailable")
        if chall is None:
            return _review(champ, reason="Challenger OCR unavailable")

        # --- Field-level comparison ---
        field_report: Dict[str, Dict[str, Any]] = {}
        agree_count = 0
        for f in _COMPARED_FIELDS:
            a = getattr(champ, f, None)
            b = getattr(chall, f, None)
            match, similarity = _compare(a, b)
            field_report[f] = {
                "champ": _serialize(a),
                "challenger": _serialize(b),
                "match": match,
                "similarity": round(similarity, 3),
            }
            if match:
                agree_count += 1

        agreement = agree_count / len(_COMPARED_FIELDS)

        # --- Math rule: total == subtotal + tax (within tolerance) ---
        math_ok, math_detail = _check_math(champ)

        # --- Merged record: prefer Champ, use Challenger to fill gaps ---
        merged = _merge(champ, chall)

        # --- Weighted confidence: Champ counts more ---
        conf_champ = _avg_conf(champ)
        conf_chall = _avg_conf(chall)
        weighted = 0.65 * conf_champ + 0.35 * conf_chall

        passes_conf = weighted >= settings.confidence_threshold
        passes_agreement = agreement >= settings.field_match_threshold
        decision = (
            InvoiceStatus.AUTO_APPROVED
            if passes_conf and passes_agreement and math_ok
            else InvoiceStatus.REVIEW_REQUIRED
        )

        report = {
            "decision": decision.value,
            "agreement_ratio": round(agreement, 3),
            "weighted_confidence": round(weighted, 3),
            "confidence_by_engine": {
                "champ": round(conf_champ, 3),
                "challenger": round(conf_chall, 3),
            },
            "thresholds": {
                "confidence": settings.confidence_threshold,
                "field_match": settings.field_match_threshold,
                "amount_tolerance": settings.amount_tolerance,
            },
            "math_check": math_detail,
            "fields": field_report,
            "reasons": _reasons(
                passes_conf, passes_agreement, math_ok, math_detail
            ),
        }

        return ValidationOutput(
            decision=decision,
            merged=merged,
            confidence_score=weighted,
            report=report,
        )


# ---------- helpers ----------
def _review(ex: InvoiceExtracted, reason: str) -> ValidationOutput:
    return ValidationOutput(
        decision=InvoiceStatus.REVIEW_REQUIRED,
        merged=ex,
        confidence_score=_avg_conf(ex),
        report={"decision": "REVIEW_REQUIRED", "reasons": [reason]},
    )


def _compare(a: Any, b: Any) -> Tuple[bool, float]:
    if a is None or b is None:
        return (a == b, 1.0 if a == b else 0.0)
    if isinstance(a, Decimal) and isinstance(b, Decimal):
        diff = abs(a - b)
        tol = Decimal(str(settings.amount_tolerance)) * max(abs(a), abs(b), Decimal("1"))
        return (diff <= tol, 1.0 if diff <= tol else 1.0 - float(diff / max(abs(a) + abs(b), Decimal("1"))))
    sa, sb = str(a).strip().lower(), str(b).strip().lower()
    if sa == sb:
        return True, 1.0
    ratio = SequenceMatcher(None, sa, sb).ratio()
    return (ratio >= 0.9, ratio)


def _serialize(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _avg_conf(ex: InvoiceExtracted) -> float:
    vals = [v for v in ex.confidence_scores.values() if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _check_math(ex: InvoiceExtracted) -> Tuple[bool, Dict[str, Any]]:
    if not ex.items or ex.total_amount is None:
        return True, {"skipped": True, "reason": "insufficient data"}
    line_sum = sum((i.amount for i in ex.items), start=Decimal("0"))
    tax = ex.tax_amount or Decimal("0")
    computed = (line_sum + tax).quantize(Decimal("0.01"))
    actual = Decimal(ex.total_amount).quantize(Decimal("0.01"))
    tol = Decimal(str(settings.amount_tolerance)) * max(actual, Decimal("1"))
    ok = abs(computed - actual) <= tol
    return ok, {
        "skipped": False,
        "line_sum": str(line_sum),
        "tax": str(tax),
        "computed_total": str(computed),
        "declared_total": str(actual),
        "within_tolerance": ok,
    }


def _merge(a: InvoiceExtracted, b: InvoiceExtracted) -> InvoiceExtracted:
    """Champ wins on conflicts; Challenger fills gaps."""
    merged = a.model_copy(deep=True)
    for f in _COMPARED_FIELDS + ("currency", "due_date"):
        if getattr(merged, f, None) is None:
            val = getattr(b, f, None)
            if val is not None:
                setattr(merged, f, val)
    if not merged.items and b.items:
        merged.items = b.items
    # Preserve both raw OCR payloads for audit
    merged.raw = {"champ": a.raw, "challenger": b.raw}
    return merged


def _reasons(conf_ok: bool, agree_ok: bool, math_ok: bool, math: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    if not conf_ok:
        reasons.append("Confidence below threshold")
    if not agree_ok:
        reasons.append("Field agreement below threshold")
    if not math_ok and not math.get("skipped"):
        reasons.append(
            f"Total mismatch: computed={math['computed_total']} declared={math['declared_total']}"
        )
    if not reasons:
        reasons.append("All checks passed")
    return reasons
