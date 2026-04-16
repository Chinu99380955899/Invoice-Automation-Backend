"""Celery application factory."""
from celery import Celery
from celery.signals import setup_logging

from app.core.config import settings
from app.core.logging import configure_logging

celery_app = Celery(
    "invoice_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue=settings.celery_task_default_queue,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=600,          # hard kill at 10 min
    task_soft_time_limit=480,     # warn at 8 min
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,   # recycle to avoid memory leaks
    broker_connection_retry_on_startup=True,
    # Dead-letter: failed tasks end up on `invoices.dlq` for inspection
    task_routes={
        "process_invoice": {"queue": settings.celery_task_default_queue},
        "post_invoice": {"queue": settings.celery_task_default_queue},
    },
    task_queue_max_priority=10,
    result_expires=60 * 60 * 24,  # keep results 24h
)


@setup_logging.connect
def _configure_worker_logging(*args, **kwargs):
    configure_logging()
