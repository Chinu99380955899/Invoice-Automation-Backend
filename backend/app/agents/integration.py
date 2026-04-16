"""Agent 5 — Integration layer.

Mock-by-default integration with SAP (final posting) and Salesforce
(vendor / PO validation). Real implementations should swap out these
adapters while preserving the same return shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Optional
from uuid import UUID

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceExtracted
from app.utils.circuit_breaker import get_breaker
from app.utils.exceptions import IntegrationError

log = get_logger(__name__)

_sap_breaker = get_breaker("sap", fail_max=5, reset_timeout=60)
_sf_breaker = get_breaker("salesforce", fail_max=5, reset_timeout=60)


# ---------- Salesforce vendor/PO validation ----------
@dataclass
class SalesforceValidationInput:
    invoice: InvoiceExtracted


@dataclass
class SalesforceValidationOutput:
    vendor_id: Optional[str]
    vendor_valid: bool
    po_valid: bool
    message: str


class SalesforceValidationAgent(
    BaseAgent[SalesforceValidationInput, SalesforceValidationOutput]
):
    name = "salesforce_validation"

    def _run(self, inputs: SalesforceValidationInput) -> SalesforceValidationOutput:
        if settings.use_mock_integrations:
            return _mock_salesforce(inputs.invoice)
        return self._real(inputs)

    @_sf_breaker
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def _real(
        self, inputs: SalesforceValidationInput
    ) -> SalesforceValidationOutput:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{settings.salesforce_api_url}/validate-vendor",
                    json={
                        "vendor_name": inputs.invoice.vendor_name,
                        "purchase_order": inputs.invoice.purchase_order,
                    },
                    headers={"Authorization": f"Bearer {settings.salesforce_api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return SalesforceValidationOutput(
                    vendor_id=data.get("vendor_id"),
                    vendor_valid=bool(data.get("vendor_valid")),
                    po_valid=bool(data.get("po_valid")),
                    message=data.get("message", "ok"),
                )
        except Exception as exc:
            raise IntegrationError(f"Salesforce validation failed: {exc}") from exc


# ---------- SAP posting ----------
@dataclass
class SAPPostingInput:
    invoice_id: UUID
    invoice: InvoiceExtracted
    salesforce_vendor_id: Optional[str] = None


@dataclass
class SAPPostingOutput:
    sap_document_id: str
    message: str


class SAPPostingAgent(BaseAgent[SAPPostingInput, SAPPostingOutput]):
    name = "sap_posting"

    def _run(self, inputs: SAPPostingInput) -> SAPPostingOutput:
        if settings.use_mock_integrations:
            return _mock_sap_post(inputs)
        return self._real(inputs)

    @_sap_breaker
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def _real(self, inputs: SAPPostingInput) -> SAPPostingOutput:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{settings.sap_api_url}/invoices",
                    json={
                        "invoice_id": str(inputs.invoice_id),
                        "vendor_id": inputs.salesforce_vendor_id,
                        "invoice_number": inputs.invoice.invoice_number,
                        "total": str(inputs.invoice.total_amount),
                        "currency": inputs.invoice.currency or "USD",
                        "invoice_date": (
                            inputs.invoice.invoice_date.isoformat()
                            if inputs.invoice.invoice_date
                            else None
                        ),
                    },
                    headers={"Authorization": f"Bearer {settings.sap_api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return SAPPostingOutput(
                    sap_document_id=data["document_id"],
                    message=data.get("message", "posted"),
                )
        except Exception as exc:
            raise IntegrationError(f"SAP posting failed: {exc}") from exc


# ------- Mocks -------
def _mock_salesforce(invoice: InvoiceExtracted) -> SalesforceValidationOutput:
    r = Random(str(invoice.vendor_name or ""))
    vendor_valid = r.random() > 0.02  # 98% of vendors validate
    po_valid = True if not invoice.purchase_order else r.random() > 0.05
    return SalesforceValidationOutput(
        vendor_id=f"SF-VEND-{abs(hash(invoice.vendor_name or '')) % 100000:05d}",
        vendor_valid=vendor_valid,
        po_valid=po_valid,
        message="mock_ok" if vendor_valid and po_valid else "mock_partial",
    )


def _mock_sap_post(inputs: SAPPostingInput) -> SAPPostingOutput:
    doc_id = f"SAP-{abs(hash(str(inputs.invoice_id))) % 10_000_000:07d}"
    return SAPPostingOutput(sap_document_id=doc_id, message="mock_posted")
