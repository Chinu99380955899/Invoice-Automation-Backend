"""Unit tests for the validation agent decision logic."""
from decimal import Decimal

from app.agents.validation import ValidationAgent, ValidationInput
from app.db.models.invoice import InvoiceStatus
from app.schemas.invoice import InvoiceExtracted, InvoiceItemCreate


def _extracted(variant: str = "a") -> InvoiceExtracted:
    return InvoiceExtracted(
        vendor_name="Acme Supplies Ltd",
        invoice_number="INV-12345",
        total_amount=Decimal("108.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("8.00"),
        currency="USD",
        items=[
            InvoiceItemCreate(
                line_number=1,
                description="Widget",
                quantity=Decimal("2"),
                unit_price=Decimal("50.00"),
                amount=Decimal("100.00"),
            )
        ],
        confidence_scores={
            "vendor_name": 0.95 if variant == "a" else 0.92,
            "invoice_number": 0.97,
            "total_amount": 0.96,
            "subtotal": 0.92,
            "tax_amount": 0.91,
        },
    )


def test_auto_approves_when_both_engines_agree():
    a = _extracted("a")
    b = _extracted("b")
    result = ValidationAgent().execute(ValidationInput(champ=a, challenger=b))
    assert result.success
    assert result.output.decision == InvoiceStatus.AUTO_APPROVED


def test_review_when_totals_disagree():
    a = _extracted("a")
    b = a.model_copy()
    b.total_amount = Decimal("999.00")
    result = ValidationAgent().execute(ValidationInput(champ=a, challenger=b))
    assert result.success
    assert result.output.decision == InvoiceStatus.REVIEW_REQUIRED


def test_degrades_gracefully_when_one_engine_missing():
    a = _extracted("a")
    result = ValidationAgent().execute(ValidationInput(champ=a, challenger=None))
    assert result.success
    assert result.output.decision == InvoiceStatus.REVIEW_REQUIRED


def test_math_check_detects_wrong_total():
    a = _extracted("a")
    a.total_amount = Decimal("500.00")  # doesn't match 100 + 8
    b = _extracted("b")
    b.total_amount = Decimal("500.00")
    result = ValidationAgent().execute(ValidationInput(champ=a, challenger=b))
    assert result.output.decision == InvoiceStatus.REVIEW_REQUIRED
    assert any(
        "mismatch" in r.lower() or "total" in r.lower()
        for r in result.output.report["reasons"]
    )
