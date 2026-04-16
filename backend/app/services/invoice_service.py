"""Invoice service: CRUD, filtering, stats, review actions."""
from datetime import datetime, timezone, timedelta
from math import ceil
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.invoice import (
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    LogLevel,
    ProcessingLog,
)
from app.schemas.invoice import (
    DashboardStats,
    InvoiceFilters,
    InvoiceUpdate,
)
from app.utils.exceptions import (
    ConflictError,
    DuplicateInvoiceError,
    NotFoundError,
)


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- Queries ----------
    def get(self, invoice_id: UUID) -> Invoice:
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice

    def get_with_logs(self, invoice_id: UUID) -> Invoice:
        invoice = self.db.scalar(
            select(Invoice)
            .options(selectinload(Invoice.items), selectinload(Invoice.logs))
            .where(Invoice.id == invoice_id)
        )
        if not invoice:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice

    def get_by_hash(self, file_hash: str) -> Optional[Invoice]:
        return self.db.scalar(select(Invoice).where(Invoice.file_hash == file_hash))

    def list(
        self,
        filters: InvoiceFilters,
        page: int = 1,
        size: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> Tuple[List[Invoice], int]:
        query = select(Invoice)
        count_query = select(func.count(Invoice.id))

        conditions = []
        if filters.status:
            conditions.append(Invoice.status == filters.status)
        if filters.vendor_name:
            conditions.append(Invoice.vendor_name.ilike(f"%{filters.vendor_name}%"))
        if filters.invoice_number:
            conditions.append(
                Invoice.invoice_number.ilike(f"%{filters.invoice_number}%")
            )
        if filters.date_from:
            conditions.append(Invoice.invoice_date >= filters.date_from)
        if filters.date_to:
            conditions.append(Invoice.invoice_date <= filters.date_to)
        if filters.search:
            s = f"%{filters.search}%"
            conditions.append(
                or_(
                    Invoice.vendor_name.ilike(s),
                    Invoice.invoice_number.ilike(s),
                    Invoice.original_filename.ilike(s),
                    Invoice.purchase_order.ilike(s),
                )
            )

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # Safe sort whitelist
        sort_map = {
            "created_at": Invoice.created_at,
            "invoice_date": Invoice.invoice_date,
            "vendor_name": Invoice.vendor_name,
            "total_amount": Invoice.total_amount,
            "status": Invoice.status,
        }
        sort_col = sort_map.get(sort_by, Invoice.created_at)
        query = query.order_by(
            sort_col.desc() if sort_dir.lower() == "desc" else sort_col.asc()
        )

        total = self.db.scalar(count_query) or 0
        offset = max(0, (page - 1) * size)
        items = list(
            self.db.scalars(
                query.options(selectinload(Invoice.items))
                .offset(offset)
                .limit(size)
            )
        )
        return items, total

    # ---------- Mutations ----------
    def create(
        self,
        *,
        original_filename: str,
        storage_path: str,
        file_hash: str,
        file_size_bytes: int,
        mime_type: str,
        uploaded_by_id: UUID,
    ) -> Invoice:
        if self.get_by_hash(file_hash):
            raise DuplicateInvoiceError()
        invoice = Invoice(
            original_filename=original_filename,
            storage_path=storage_path,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            uploaded_by_id=uploaded_by_id,
            status=InvoiceStatus.UPLOADED,
        )
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def update_fields(
        self, invoice_id: UUID, updates: InvoiceUpdate, reviewer_id: UUID
    ) -> Invoice:
        invoice = self.get(invoice_id)
        payload = updates.model_dump(exclude_unset=True, exclude={"items"})
        for key, value in payload.items():
            setattr(invoice, key, value)

        if updates.items is not None:
            # Replace line items atomically
            self.db.query(InvoiceItem).filter(
                InvoiceItem.invoice_id == invoice.id
            ).delete(synchronize_session=False)
            for item in updates.items:
                self.db.add(
                    InvoiceItem(invoice_id=invoice.id, **item.model_dump())
                )

        invoice.reviewed_by_id = reviewer_id
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def transition_status(
        self,
        invoice_id: UUID,
        new_status: InvoiceStatus,
        reviewer_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> Invoice:
        invoice = self.get(invoice_id)
        _assert_transition(invoice.status, new_status)
        invoice.status = new_status
        if reviewer_id:
            invoice.reviewed_by_id = reviewer_id
        if notes:
            invoice.review_notes = notes
        if new_status == InvoiceStatus.POSTED:
            invoice.posted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def add_log(
        self,
        invoice_id: UUID,
        *,
        agent: str,
        level: LogLevel = LogLevel.INFO,
        message: str,
        duration_ms: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> ProcessingLog:
        log = ProcessingLog(
            invoice_id=invoice_id,
            agent=agent,
            level=level,
            message=message,
            duration_ms=duration_ms,
            extra=extra,
        )
        self.db.add(log)
        self.db.commit()
        return log

    # ---------- Stats ----------
    def dashboard_stats(self) -> DashboardStats:
        counts_q = select(Invoice.status, func.count(Invoice.id)).group_by(
            Invoice.status
        )
        counts = {s.value: 0 for s in InvoiceStatus}
        for status, count in self.db.execute(counts_q).all():
            counts[status.value] = count

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        processed_today = (
            self.db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.updated_at >= today_start,
                    Invoice.status.in_(
                        [
                            InvoiceStatus.AUTO_APPROVED,
                            InvoiceStatus.APPROVED,
                            InvoiceStatus.POSTED,
                        ]
                    ),
                )
            )
            or 0
        )

        avg_seconds_row = self.db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch", Invoice.updated_at - Invoice.created_at
                    )
                )
            ).where(Invoice.status != InvoiceStatus.UPLOADED)
        ).scalar()
        avg_seconds = float(avg_seconds_row or 0.0)

        return DashboardStats(
            total=sum(counts.values()),
            uploaded=counts["UPLOADED"],
            processing=counts["PROCESSING"],
            auto_approved=counts["AUTO_APPROVED"],
            review_required=counts["REVIEW_REQUIRED"],
            approved=counts["APPROVED"],
            rejected=counts["REJECTED"],
            posted=counts["POSTED"],
            failed=counts["FAILED"],
            processed_today=processed_today,
            avg_processing_seconds=round(avg_seconds, 2),
        )


# ------- Status machine -------
_ALLOWED_TRANSITIONS = {
    InvoiceStatus.UPLOADED: {InvoiceStatus.PROCESSING, InvoiceStatus.FAILED},
    InvoiceStatus.PROCESSING: {
        InvoiceStatus.AUTO_APPROVED,
        InvoiceStatus.REVIEW_REQUIRED,
        InvoiceStatus.FAILED,
    },
    InvoiceStatus.AUTO_APPROVED: {InvoiceStatus.POSTED, InvoiceStatus.FAILED},
    InvoiceStatus.REVIEW_REQUIRED: {
        InvoiceStatus.APPROVED,
        InvoiceStatus.REJECTED,
        InvoiceStatus.PROCESSING,  # reprocess
    },
    InvoiceStatus.APPROVED: {InvoiceStatus.POSTED, InvoiceStatus.FAILED},
    InvoiceStatus.FAILED: {InvoiceStatus.PROCESSING},  # retry
    InvoiceStatus.POSTED: set(),
    InvoiceStatus.REJECTED: set(),
}


def _assert_transition(current: InvoiceStatus, target: InvoiceStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ConflictError(
            f"Cannot transition from {current.value} to {target.value}"
        )
