"""Invoice upload, listing, detail endpoints."""
from datetime import date
from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.invoice import InvoiceStatus
from app.schemas.common import Page
from app.schemas.invoice import (
    DashboardStats,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceRead,
    InvoiceUploadResponse,
)
from app.services.invoice_service import InvoiceService
from app.services.storage_service import get_storage
from app.utils.exceptions import (
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.utils.hashing import sha256_of_bytes

router = APIRouter(prefix="/invoices", tags=["invoices"])
log = get_logger(__name__)


def _validate_upload(file: UploadFile, size: int) -> None:
    if size > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"File exceeds max size of {settings.max_upload_size_mb} MB",
            details={"size": size, "max": settings.max_upload_bytes},
        )
    filename = (file.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in settings.allowed_extensions_list:
        raise UnsupportedFileTypeError(
            f"Extension '.{ext}' is not allowed",
            details={"allowed": settings.allowed_extensions_list},
        )


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_invoice(
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(..., description="Invoice file (PDF/PNG/JPEG/TIFF)"),
) -> InvoiceUploadResponse:
    content = await file.read()
    _validate_upload(file, len(content))

    file_hash = sha256_of_bytes(content)
    storage = get_storage()
    # Use hash-based keys for idempotency & dedup-friendly storage
    key = f"invoices/{file_hash[:2]}/{file_hash}_{file.filename}"
    storage_path = storage.save(key, content)

    service = InvoiceService(db)
    invoice = service.create(
        original_filename=file.filename or "unknown",
        storage_path=storage_path,
        file_hash=file_hash,
        file_size_bytes=len(content),
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by_id=user.id,
    )

    # Queue async processing — worker is decoupled so uploads never block
    from app.workers.tasks import process_invoice_task  # local to avoid cycles

    process_invoice_task.apply_async(
        args=[str(invoice.id)],
        task_id=f"invoice-{invoice.id}",
    )

    log.info(
        "invoice_uploaded",
        invoice_id=str(invoice.id),
        filename=file.filename,
        size=len(content),
    )
    return InvoiceUploadResponse(
        id=invoice.id,
        original_filename=invoice.original_filename,
        status=invoice.status,
    )


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: DBSession, _user: CurrentUser) -> DashboardStats:
    return InvoiceService(db).dashboard_stats()


@router.get("", response_model=Page[InvoiceRead])
def list_invoices(
    db: DBSession,
    _user: CurrentUser,
    status_filter: Optional[InvoiceStatus] = Query(None, alias="status"),
    vendor_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> Page[InvoiceRead]:
    filters = InvoiceFilters(
        status=status_filter,
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    items, total = InvoiceService(db).list(
        filters, page=page, size=size, sort_by=sort_by, sort_dir=sort_dir
    )
    return Page[InvoiceRead](
        items=[InvoiceRead.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
        pages=max(1, ceil(total / size)) if total else 1,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(
    invoice_id: UUID, db: DBSession, _user: CurrentUser
) -> InvoiceDetail:
    invoice = InvoiceService(db).get_with_logs(invoice_id)
    return InvoiceDetail.model_validate(invoice)
