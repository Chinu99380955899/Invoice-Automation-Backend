"""Service-layer tests for InvoiceService: dedup, filters, status machine."""
from uuid import uuid4

import pytest

from app.db.models.invoice import InvoiceStatus
from app.db.models.user import User, UserRole
from app.schemas.invoice import InvoiceFilters
from app.services.invoice_service import InvoiceService
from app.utils.exceptions import ConflictError, DuplicateInvoiceError


def _user(db):
    u = User(
        email="u@test.local",
        full_name="Tester",
        hashed_password="x",
        role=UserRole.UPLOADER,
    )
    db.add(u)
    db.commit()
    return u


def test_dedup_on_same_hash(db_session):
    user = _user(db_session)
    svc = InvoiceService(db_session)
    svc.create(
        original_filename="a.pdf",
        storage_path="/tmp/a.pdf",
        file_hash="hash123",
        file_size_bytes=1000,
        mime_type="application/pdf",
        uploaded_by_id=user.id,
    )
    with pytest.raises(DuplicateInvoiceError):
        svc.create(
            original_filename="b.pdf",
            storage_path="/tmp/b.pdf",
            file_hash="hash123",
            file_size_bytes=2000,
            mime_type="application/pdf",
            uploaded_by_id=user.id,
        )


def test_status_transition_enforced(db_session):
    user = _user(db_session)
    svc = InvoiceService(db_session)
    inv = svc.create(
        original_filename="a.pdf",
        storage_path="/tmp/a.pdf",
        file_hash="h1",
        file_size_bytes=1,
        mime_type="application/pdf",
        uploaded_by_id=user.id,
    )
    # UPLOADED → POSTED is not allowed
    with pytest.raises(ConflictError):
        svc.transition_status(inv.id, InvoiceStatus.POSTED)
    # UPLOADED → PROCESSING is allowed
    svc.transition_status(inv.id, InvoiceStatus.PROCESSING)


def test_filter_by_status(db_session):
    user = _user(db_session)
    svc = InvoiceService(db_session)
    for i in range(3):
        svc.create(
            original_filename=f"f{i}.pdf",
            storage_path=f"/tmp/{i}.pdf",
            file_hash=f"hash-{i}",
            file_size_bytes=10,
            mime_type="application/pdf",
            uploaded_by_id=user.id,
        )

    items, total = svc.list(InvoiceFilters(status=InvoiceStatus.UPLOADED))
    assert total == 3
    assert all(i.status == InvoiceStatus.UPLOADED for i in items)

    items2, total2 = svc.list(InvoiceFilters(status=InvoiceStatus.POSTED))
    assert total2 == 0
    assert items2 == []
