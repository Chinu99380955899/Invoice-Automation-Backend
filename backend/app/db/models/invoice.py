"""Invoice-related ORM models."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class InvoiceStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    AUTO_APPROVED = "AUTO_APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POSTED = "POSTED"
    FAILED = "FAILED"


class OCREngine(str, Enum):
    CHAMP = "CHAMP"           # Azure Document Intelligence
    CHALLENGER = "CHALLENGER"  # PaddleOCR


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


class Invoice(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "invoices"

    # --- File metadata ---
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # --- Extracted invoice data (authoritative after validation) ---
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    purchase_order: Mapped[Optional[str]] = mapped_column(String(128))

    # --- Raw OCR outputs (audit trail for A/B comparison) ---
    champ_ocr_raw: Mapped[Optional[dict]] = mapped_column(JSONB)
    challenger_ocr_raw: Mapped[Optional[dict]] = mapped_column(JSONB)
    validation_report: Mapped[Optional[dict]] = mapped_column(JSONB)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    # --- Workflow ---
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- Integrations ---
    sap_document_id: Mapped[Optional[str]] = mapped_column(String(128))
    salesforce_vendor_id: Mapped[Optional[str]] = mapped_column(String(128))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Ownership ---
    uploaded_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewed_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    items: Mapped[List["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    logs: Mapped[List["ProcessingLog"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProcessingLog.created_at",
    )

    __table_args__ = (
        Index("ix_invoices_status_created", "status", "created_at"),
        Index("ix_invoices_vendor_number", "vendor_name", "invoice_number"),
    )


class InvoiceItem(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class ProcessingLog(Base, UUIDPrimaryKey, TimestampMixin):
    """Append-only log of every pipeline step — serves as audit trail."""

    __tablename__ = "processing_logs"

    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[LogLevel] = mapped_column(
        SAEnum(LogLevel, name="log_level"),
        default=LogLevel.INFO,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    extra: Mapped[Optional[dict]] = mapped_column(JSONB)

    invoice: Mapped[Invoice] = relationship(back_populates="logs")
