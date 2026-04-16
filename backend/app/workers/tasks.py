"""Celery tasks — thin wrappers that delegate to the pipeline orchestrator.

Key properties:
- idempotent (keyed by invoice_id)
- retry with exponential backoff (≥ 3 attempts)
- terminal failures routed to the dead-letter queue for post-mortem
"""
from uuid import UUID

from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from app.agents.integration import SAPPostingAgent, SAPPostingInput
from app.agents.pipeline import run_pipeline
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.invoice import InvoiceStatus, LogLevel
from app.db.session import session_scope
from app.schemas.invoice import InvoiceExtracted, InvoiceItemCreate
from app.services.invoice_service import InvoiceService
from app.workers.celery_app import celery_app

log = get_logger("worker")


@celery_app.task(
    name="process_invoice",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=None,  # overridden per-call from settings
    acks_late=True,
)
def process_invoice_task(self, invoice_id: str):
    """Full OCR + validation pipeline for a single invoice."""
    max_retries = settings.celery_task_max_retries
    inv_uuid = UUID(invoice_id)

    try:
        with session_scope() as db:
            result = run_pipeline(inv_uuid, db)
            InvoiceService(db).add_log(
                inv_uuid,
                agent="pipeline",
                level=LogLevel.INFO,
                message=f"Pipeline finished with decision {result.decision.value}",
                extra={"confidence": result.confidence_score},
            )
            log.info("pipeline_done", invoice_id=invoice_id,
                     decision=result.decision.value)

        # Auto-post if the validation agent approved
        if result.decision == InvoiceStatus.AUTO_APPROVED:
            post_invoice_task.apply_async(args=[invoice_id])

        return {
            "invoice_id": invoice_id,
            "decision": result.decision.value,
            "confidence": result.confidence_score,
        }

    except SoftTimeLimitExceeded:
        log.error("task_soft_timeout", invoice_id=invoice_id)
        _mark_failed(invoice_id, "Soft time limit exceeded")
        raise

    except Exception as exc:
        attempt = self.request.retries + 1
        log.warning(
            "task_retry",
            invoice_id=invoice_id,
            attempt=attempt,
            max_retries=max_retries,
            error=str(exc),
        )
        with session_scope() as db:
            inv = db.get(type(InvoiceService(db).get(inv_uuid)), inv_uuid) if False else None
            # Track retry count on the invoice row (simple, queryable)
            from app.db.models.invoice import Invoice

            invoice = db.get(Invoice, inv_uuid)
            if invoice:
                invoice.retry_count = attempt
                invoice.error_message = str(exc)[:2000]

        if self.request.retries >= max_retries:
            _mark_failed(invoice_id, f"Max retries exceeded: {exc}")
            # Send to DLQ for manual inspection
            dead_letter_task.apply_async(
                args=[invoice_id, str(exc)], queue="invoices.dlq"
            )
            raise MaxRetriesExceededError(str(exc)) from exc

        raise self.retry(exc=exc, countdown=min(60, 2 ** attempt))


@celery_app.task(
    name="post_invoice",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def post_invoice_task(self, invoice_id: str):
    """Post an approved invoice to SAP."""
    inv_uuid = UUID(invoice_id)
    with session_scope() as db:
        svc = InvoiceService(db)
        invoice = svc.get(inv_uuid)
        if invoice.status not in {
            InvoiceStatus.AUTO_APPROVED,
            InvoiceStatus.APPROVED,
        }:
            log.warning(
                "post_invoice_skipped",
                invoice_id=invoice_id,
                status=invoice.status.value,
            )
            return {"skipped": True, "reason": f"bad status: {invoice.status.value}"}

        merged = _rebuild_extracted(invoice)

        agent = SAPPostingAgent()
        res = agent.execute(
            SAPPostingInput(
                invoice_id=invoice.id,
                invoice=merged,
                salesforce_vendor_id=invoice.salesforce_vendor_id,
            )
        )
        if not res.success or res.output is None:
            svc.add_log(
                invoice.id,
                agent=res.agent,
                level=LogLevel.ERROR,
                message=f"SAP posting failed: {res.error}",
                duration_ms=res.duration_ms,
            )
            raise RuntimeError(res.error or "SAP posting failed")

        invoice.sap_document_id = res.output.sap_document_id
        svc.transition_status(invoice.id, InvoiceStatus.POSTED)
        svc.add_log(
            invoice.id,
            agent=res.agent,
            level=LogLevel.INFO,
            message=f"Posted to SAP as {res.output.sap_document_id}",
            duration_ms=res.duration_ms,
        )
        return {"invoice_id": invoice_id, "sap_document_id": res.output.sap_document_id}


@celery_app.task(name="dead_letter", queue="invoices.dlq")
def dead_letter_task(invoice_id: str, error: str):
    """Terminal failure — park for human follow-up."""
    log.error("dead_letter", invoice_id=invoice_id, error=error)
    with session_scope() as db:
        InvoiceService(db).add_log(
            UUID(invoice_id),
            agent="dead_letter",
            level=LogLevel.ERROR,
            message=f"Task sent to DLQ: {error}",
        )


# ---------- helpers ----------
def _mark_failed(invoice_id: str, message: str) -> None:
    try:
        with session_scope() as db:
            from app.db.models.invoice import Invoice

            invoice = db.get(Invoice, UUID(invoice_id))
            if invoice:
                invoice.status = InvoiceStatus.FAILED
                invoice.error_message = message[:2000]
                InvoiceService(db).add_log(
                    invoice.id,
                    agent="pipeline",
                    level=LogLevel.ERROR,
                    message=message,
                )
    except Exception as exc:  # pragma: no cover - best effort
        log.error("mark_failed_error", invoice_id=invoice_id, error=str(exc))


def _rebuild_extracted(invoice) -> InvoiceExtracted:
    """Reconstruct an InvoiceExtracted from persisted invoice rows."""
    return InvoiceExtracted(
        vendor_name=invoice.vendor_name,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        purchase_order=invoice.purchase_order,
        items=[
            InvoiceItemCreate(
                line_number=i.line_number,
                description=i.description,
                quantity=i.quantity,
                unit_price=i.unit_price,
                amount=i.amount,
                tax_rate=i.tax_rate,
            )
            for i in invoice.items
        ],
    )
