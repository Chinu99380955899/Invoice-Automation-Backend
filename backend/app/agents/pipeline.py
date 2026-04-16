"""Orchestrates the 5-agent pipeline end-to-end.

This module is transport-agnostic — it's invoked from the Celery task but
could equally be called from a script or test. Each step is wrapped in
BaseAgent.execute() so failures degrade gracefully: a failed OCR pass is
logged and the pipeline continues with whatever data is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.agents.challenger_ocr import ChallengerOCRAgent, ChallengerOCRInput
from app.agents.champ_ocr import ChampOCRAgent, ChampOCRInput
from app.agents.integration import (
    SalesforceValidationAgent,
    SalesforceValidationInput,
)
from app.agents.preprocessing import PreprocessingAgent, PreprocessingInput
from app.agents.validation import ValidationAgent, ValidationInput, ValidationOutput
from app.core.logging import get_logger
from app.db.models.invoice import (
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    LogLevel,
)
from app.services.invoice_service import InvoiceService
from app.services.storage_service import get_storage

log = get_logger(__name__)


@dataclass
class PipelineResult:
    invoice_id: UUID
    decision: InvoiceStatus
    confidence_score: float


def run_pipeline(invoice_id: UUID, db) -> PipelineResult:
    """Execute the complete pipeline for a single invoice."""
    svc = InvoiceService(db)
    invoice = svc.get(invoice_id)

    # --- Mark processing ---
    if invoice.status in {InvoiceStatus.UPLOADED, InvoiceStatus.FAILED,
                          InvoiceStatus.REVIEW_REQUIRED}:
        invoice = svc.transition_status(invoice.id, InvoiceStatus.PROCESSING)

    # --- Load file ---
    try:
        file_bytes = get_storage().read(_storage_key(invoice.storage_path))
    except Exception as exc:
        svc.add_log(
            invoice.id,
            agent="pipeline",
            level=LogLevel.ERROR,
            message=f"Failed to load file: {exc}",
        )
        invoice.error_message = f"Storage read failed: {exc}"
        invoice.status = InvoiceStatus.FAILED
        db.commit()
        raise

    # --- 1. Preprocessing ---
    pre = PreprocessingAgent().execute(
        PreprocessingInput(file_bytes=file_bytes, mime_type=invoice.mime_type)
    )
    svc.add_log(
        invoice.id,
        agent=pre.agent,
        level=LogLevel.INFO if pre.success else LogLevel.WARNING,
        message=("Preprocessed " + (str(pre.output.page_count) + " pages" if pre.output else "failed"))
                if pre.success else f"Preprocessing failed: {pre.error}",
        duration_ms=pre.duration_ms,
    )

    encoded_pages = pre.output.encoded_pngs if pre.success and pre.output else []

    # --- 2 & 3. Dual OCR (run sequentially in worker; parallelism is at task level) ---
    champ_res = ChampOCRAgent().execute(
        ChampOCRInput(file_bytes=file_bytes, mime_type=invoice.mime_type,
                      file_hash=invoice.file_hash)
    )
    svc.add_log(
        invoice.id,
        agent=champ_res.agent,
        level=LogLevel.INFO if champ_res.success else LogLevel.ERROR,
        message="Champ OCR ok" if champ_res.success else f"Champ OCR failed: {champ_res.error}",
        duration_ms=champ_res.duration_ms,
    )

    chall_res = ChallengerOCRAgent().execute(
        ChallengerOCRInput(
            encoded_pngs=encoded_pages or [file_bytes],
            file_hash=invoice.file_hash,
        )
    )
    svc.add_log(
        invoice.id,
        agent=chall_res.agent,
        level=LogLevel.INFO if chall_res.success else LogLevel.ERROR,
        message="Challenger OCR ok" if chall_res.success else f"Challenger OCR failed: {chall_res.error}",
        duration_ms=chall_res.duration_ms,
    )

    # --- 4. Validation ---
    val_res = ValidationAgent().execute(
        ValidationInput(
            champ=champ_res.output if champ_res.success else None,
            challenger=chall_res.output if chall_res.success else None,
        )
    )
    if not val_res.success or val_res.output is None:
        invoice.error_message = f"Validation failed: {val_res.error}"
        invoice.status = InvoiceStatus.FAILED
        db.commit()
        svc.add_log(
            invoice.id,
            agent=val_res.agent,
            level=LogLevel.ERROR,
            message=invoice.error_message,
            duration_ms=val_res.duration_ms,
        )
        raise RuntimeError(invoice.error_message)

    validated: ValidationOutput = val_res.output

    # --- Persist merged data + OCR artifacts ---
    merged = validated.merged
    invoice.vendor_name = merged.vendor_name
    invoice.invoice_number = merged.invoice_number
    invoice.invoice_date = merged.invoice_date
    invoice.due_date = merged.due_date
    invoice.currency = merged.currency
    invoice.subtotal = merged.subtotal
    invoice.tax_amount = merged.tax_amount
    invoice.total_amount = merged.total_amount
    invoice.purchase_order = merged.purchase_order
    invoice.confidence_score = round(validated.confidence_score, 4)
    invoice.champ_ocr_raw = (
        champ_res.output.model_dump(mode="json") if champ_res.output else None
    )
    invoice.challenger_ocr_raw = (
        chall_res.output.model_dump(mode="json") if chall_res.output else None
    )
    invoice.validation_report = validated.report

    # Replace items
    db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).delete()
    for item in merged.items:
        db.add(InvoiceItem(invoice_id=invoice.id, **item.model_dump()))

    invoice.status = validated.decision
    db.commit()

    svc.add_log(
        invoice.id,
        agent=val_res.agent,
        level=LogLevel.INFO,
        message=f"Validation decision: {validated.decision.value}",
        duration_ms=val_res.duration_ms,
        extra={"report": validated.report},
    )

    # --- 5a. Salesforce vendor validation (informational, non-blocking) ---
    sf_res = SalesforceValidationAgent().execute(
        SalesforceValidationInput(invoice=merged)
    )
    if sf_res.success and sf_res.output:
        invoice.salesforce_vendor_id = sf_res.output.vendor_id
        db.commit()
    svc.add_log(
        invoice.id,
        agent=sf_res.agent,
        level=LogLevel.INFO if sf_res.success else LogLevel.WARNING,
        message=(
            f"Salesforce: vendor_valid={sf_res.output.vendor_valid}"
            if sf_res.success and sf_res.output
            else f"Salesforce check failed: {sf_res.error}"
        ),
        duration_ms=sf_res.duration_ms,
    )

    return PipelineResult(
        invoice_id=invoice.id,
        decision=invoice.status,
        confidence_score=float(invoice.confidence_score or 0.0),
    )


def _storage_key(storage_path: str) -> str:
    """Extract the relative key for the storage backend."""
    if storage_path.startswith("azure://"):
        # azure://container/key
        return storage_path.split("/", 3)[-1]
    # Local paths are stored as absolute — return a path relative to storage root.
    from app.core.config import settings
    from pathlib import Path

    root = Path(settings.local_storage_path).resolve()
    try:
        return str(Path(storage_path).resolve().relative_to(root))
    except ValueError:
        return storage_path
