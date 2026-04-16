"""Seed sample invoices for local development / demos.

Usage:
    python -m scripts.seed_sample_data

Generates fake PDF-like payloads, uploads them through the same service
code path used by the real API, and lets the async worker process them.
"""
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import session_scope  # noqa: E402
from app.services.invoice_service import InvoiceService  # noqa: E402
from app.services.storage_service import get_storage  # noqa: E402
from app.services.user_service import UserService  # noqa: E402
from app.utils.exceptions import DuplicateInvoiceError  # noqa: E402


SAMPLE_COUNT = int(os.environ.get("SAMPLE_COUNT", "10"))


def main() -> None:
    storage = get_storage()
    with session_scope() as db:
        admin = UserService(db).ensure_seed_admin()

        created = 0
        for i in range(SAMPLE_COUNT):
            payload = f"SAMPLE_INVOICE_{uuid4()}".encode() * 50
            file_hash = uuid4().hex.ljust(64, "0")[:64]
            key = f"invoices/{file_hash[:2]}/{file_hash}_sample-{i}.pdf"
            path = storage.save(key, payload)

            try:
                inv = InvoiceService(db).create(
                    original_filename=f"sample-invoice-{i:03d}.pdf",
                    storage_path=path,
                    file_hash=file_hash,
                    file_size_bytes=len(payload),
                    mime_type="application/pdf",
                    uploaded_by_id=admin.id,
                )
                created += 1
                print(f"[+] {inv.id} — sample-invoice-{i:03d}.pdf")
            except DuplicateInvoiceError:
                continue

    print(f"\nDone — created {created} sample invoices.")
    print("If a worker is running, they will be processed automatically.")


if __name__ == "__main__":
    main()
