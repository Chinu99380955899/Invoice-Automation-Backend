"""Agent 2 — Champ OCR: Azure Document Intelligence (prebuilt-invoice).

Uses the official Azure SDK when credentials are configured; otherwise falls
back to a deterministic mock that produces realistic-looking output. The
circuit breaker prevents repeated outages from cascading through the queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from random import Random
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceExtracted, InvoiceItemCreate
from app.utils.circuit_breaker import get_breaker
from app.utils.exceptions import OCRFailureError

log = get_logger(__name__)
_breaker = get_breaker("azure_di", fail_max=5, reset_timeout=60)


@dataclass
class ChampOCRInput:
    file_bytes: bytes
    mime_type: str
    file_hash: str  # for deterministic mock seeding


class ChampOCRAgent(BaseAgent[ChampOCRInput, InvoiceExtracted]):
    name = "champ_ocr_azure"

    def _run(self, inputs: ChampOCRInput) -> InvoiceExtracted:
        if settings.use_mock_azure_ocr or not (
            settings.azure_di_endpoint and settings.azure_di_key
        ):
            return _mock_extract(inputs.file_hash, engine="champ")
        return self._real_extract(inputs)

    @_breaker
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _real_extract(self, inputs: ChampOCRInput) -> InvoiceExtracted:
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential

            client = DocumentAnalysisClient(
                endpoint=settings.azure_di_endpoint,
                credential=AzureKeyCredential(settings.azure_di_key),
            )
            poller = client.begin_analyze_document(
                model_id=settings.azure_di_model, document=inputs.file_bytes
            )
            result = poller.result()
        except Exception as exc:
            log.error("azure_di_failure", error=str(exc))
            raise OCRFailureError(f"Azure DI failure: {exc}") from exc

        return _from_azure_result(result)


# ------- Helpers -------
def _field(doc, name: str, default=None):
    f = doc.fields.get(name) if doc and hasattr(doc, "fields") else None
    if not f:
        return default, 0.0
    return (
        f.value if f.value is not None else (f.content or default),
        float(getattr(f, "confidence", 0.0) or 0.0),
    )


def _from_azure_result(result) -> InvoiceExtracted:
    if not result.documents:
        raise OCRFailureError("No invoice document detected by Azure DI")
    doc = result.documents[0]

    vendor, c_vendor = _field(doc, "VendorName")
    number, c_number = _field(doc, "InvoiceId")
    inv_date, c_date = _field(doc, "InvoiceDate")
    due_date, c_due = _field(doc, "DueDate")
    subtotal, c_sub = _field(doc, "SubTotal")
    tax, c_tax = _field(doc, "TotalTax")
    total, c_total = _field(doc, "InvoiceTotal")
    po, _ = _field(doc, "PurchaseOrder")
    currency, _ = _field(doc, "Currency", "USD")

    items: List[InvoiceItemCreate] = []
    line_field = doc.fields.get("Items")
    if line_field and line_field.value:
        for i, li in enumerate(line_field.value, start=1):
            li_val = li.value or {}
            desc = (li_val.get("Description") or {}).value if li_val else None
            qty = (li_val.get("Quantity") or {}).value if li_val else None
            price = (li_val.get("UnitPrice") or {}).value if li_val else None
            amt = (li_val.get("Amount") or {}).value if li_val else None
            items.append(
                InvoiceItemCreate(
                    line_number=i,
                    description=str(desc or "N/A"),
                    quantity=Decimal(str(qty or 1)),
                    unit_price=Decimal(str(getattr(price, "amount", price) or 0)),
                    amount=Decimal(str(getattr(amt, "amount", amt) or 0)),
                )
            )

    def _amount(x):
        return Decimal(str(getattr(x, "amount", x))) if x is not None else None

    return InvoiceExtracted(
        vendor_name=vendor,
        invoice_number=number,
        invoice_date=inv_date if isinstance(inv_date, date) else None,
        due_date=due_date if isinstance(due_date, date) else None,
        currency=str(getattr(total, "code", currency) or "USD") if total else currency,
        subtotal=_amount(subtotal),
        tax_amount=_amount(tax),
        total_amount=_amount(total),
        purchase_order=str(po) if po else None,
        items=items,
        confidence_scores={
            "vendor_name": c_vendor,
            "invoice_number": c_number,
            "invoice_date": c_date,
            "total_amount": c_total,
            "subtotal": c_sub,
            "tax_amount": c_tax,
        },
        raw={"engine": "azure_di", "model": settings.azure_di_model},
    )


# ------- Mock extractor -------
_VENDORS = [
    "Acme Supplies Ltd",
    "Globex Industrial",
    "Initech Software",
    "Umbrella Medical",
    "Wayne Enterprises",
    "Stark Industries",
    "Wonka Confections",
]


def _mock_extract(seed_hash: str, engine: str) -> InvoiceExtracted:
    # Seed with file hash so both engines see the same invoice content but
    # Champ and Challenger differ slightly (simulating real OCR disagreement).
    r = Random(int(seed_hash[:16], 16) ^ (0 if engine == "champ" else 7))
    vendor = r.choice(_VENDORS)
    invoice_number = f"INV-{r.randint(10000, 99999)}"
    base_date = date.today()
    items: List[InvoiceItemCreate] = []
    subtotal = Decimal("0.00")
    for i in range(1, r.randint(2, 5) + 1):
        qty = Decimal(r.randint(1, 10))
        price = Decimal(f"{r.uniform(10, 500):.2f}")
        amt = (qty * price).quantize(Decimal("0.01"))
        subtotal += amt
        items.append(
            InvoiceItemCreate(
                line_number=i,
                description=f"Service line {i} — {r.choice(['Consulting', 'Hardware', 'License', 'Shipping'])}",
                quantity=qty,
                unit_price=price,
                amount=amt,
            )
        )
    tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
    total = (subtotal + tax).quantize(Decimal("0.01"))

    # Challenger has slightly different confidence profile
    conf_base = 0.92 if engine == "champ" else 0.88
    noise = r.uniform(-0.05, 0.03)

    return InvoiceExtracted(
        vendor_name=vendor,
        invoice_number=invoice_number,
        invoice_date=base_date,
        due_date=base_date,
        currency="USD",
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=total,
        purchase_order=f"PO-{r.randint(1000, 9999)}",
        items=items,
        confidence_scores={
            "vendor_name": max(0.0, min(1.0, conf_base + noise)),
            "invoice_number": max(0.0, min(1.0, conf_base + noise)),
            "invoice_date": max(0.0, min(1.0, conf_base + noise)),
            "total_amount": max(0.0, min(1.0, conf_base + noise)),
            "subtotal": max(0.0, min(1.0, conf_base + noise - 0.02)),
            "tax_amount": max(0.0, min(1.0, conf_base + noise - 0.03)),
        },
        raw={"engine": engine, "mocked": True},
    )
