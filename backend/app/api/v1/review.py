"""Human-in-the-loop review & approval endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import DBSession, require_role
from app.core.logging import get_logger
from app.db.models.invoice import InvoiceStatus
from app.db.models.user import User, UserRole
from app.schemas.invoice import InvoiceDetail, ReviewAction
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/review", tags=["review"])
log = get_logger(__name__)

_ReviewerOrAdmin = require_role(UserRole.REVIEWER, UserRole.ADMIN)


@router.post("/{invoice_id}/action", response_model=InvoiceDetail)
def review_action(
    invoice_id: UUID,
    payload: ReviewAction,
    db: DBSession,
    user: User = Depends(_ReviewerOrAdmin),
) -> InvoiceDetail:
    service = InvoiceService(db)
    invoice = service.get(invoice_id)

    # Apply field edits first (if any)
    if payload.updates:
        invoice = service.update_fields(invoice_id, payload.updates, user.id)

    if payload.action == "APPROVE":
        invoice = service.transition_status(
            invoice_id, InvoiceStatus.APPROVED, user.id, payload.notes
        )
        # Kick off posting to SAP async
        from app.workers.tasks import post_invoice_task

        post_invoice_task.apply_async(args=[str(invoice.id)])

    elif payload.action == "REJECT":
        invoice = service.transition_status(
            invoice_id, InvoiceStatus.REJECTED, user.id, payload.notes
        )

    elif payload.action == "REPROCESS":
        invoice = service.transition_status(
            invoice_id, InvoiceStatus.PROCESSING, user.id, payload.notes
        )
        from app.workers.tasks import process_invoice_task

        process_invoice_task.apply_async(args=[str(invoice.id)])

    log.info(
        "review_action",
        invoice_id=str(invoice_id),
        action=payload.action,
        reviewer=str(user.id),
    )
    invoice = service.get_with_logs(invoice_id)
    return InvoiceDetail.model_validate(invoice)
