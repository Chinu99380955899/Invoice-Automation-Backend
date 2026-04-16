"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-04-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    user_role = postgresql.ENUM(
        "ADMIN", "REVIEWER", "UPLOADER", name="user_role"
    )
    user_role.create(op.get_bind(), checkfirst=True)

    invoice_status = postgresql.ENUM(
        "UPLOADED", "PROCESSING", "AUTO_APPROVED", "REVIEW_REQUIRED",
        "APPROVED", "REJECTED", "POSTED", "FAILED",
        name="invoice_status",
    )
    invoice_status.create(op.get_bind(), checkfirst=True)

    log_level = postgresql.ENUM(
        "INFO", "WARNING", "ERROR", "DEBUG", name="log_level"
    )
    log_level.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role",
                  postgresql.ENUM(name="user_role", create_type=False),
                  nullable=False, server_default="UPLOADER"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("invoice_number", sa.String(128)),
        sa.Column("invoice_date", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("currency", sa.String(8)),
        sa.Column("subtotal", sa.Numeric(14, 2)),
        sa.Column("tax_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("purchase_order", sa.String(128)),
        sa.Column("champ_ocr_raw", postgresql.JSONB),
        sa.Column("challenger_ocr_raw", postgresql.JSONB),
        sa.Column("validation_report", postgresql.JSONB),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("status",
                  postgresql.ENUM(name="invoice_status", create_type=False),
                  nullable=False, server_default="UPLOADED"),
        sa.Column("review_notes", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sap_document_id", sa.String(128)),
        sa.Column("salesforce_vendor_id", sa.String(128)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoices_file_hash", "invoices", ["file_hash"], unique=True)
    op.create_index("ix_invoices_vendor_name", "invoices", ["vendor_name"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_status_created", "invoices", ["status", "created_at"])
    op.create_index("ix_invoices_vendor_number", "invoices",
                    ["vendor_name", "invoice_number"])

    # --- invoice_items ---
    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # --- processing_logs ---
    op.create_table(
        "processing_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("level",
                  postgresql.ENUM(name="log_level", create_type=False),
                  nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_processing_logs_invoice_id",
                    "processing_logs", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_logs_invoice_id", table_name="processing_logs")
    op.drop_table("processing_logs")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    for idx in (
        "ix_invoices_vendor_number",
        "ix_invoices_status_created",
        "ix_invoices_status",
        "ix_invoices_invoice_date",
        "ix_invoices_invoice_number",
        "ix_invoices_vendor_name",
        "ix_invoices_file_hash",
    ):
        op.drop_index(idx, table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    for enum in ("log_level", "invoice_status", "user_role"):
        sa.Enum(name=enum).drop(op.get_bind(), checkfirst=True)
