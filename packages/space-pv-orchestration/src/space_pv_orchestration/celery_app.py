from celery import Celery

from .config import OrchestrationSettings

settings = OrchestrationSettings()
celery_app = Celery(
    "space_pv",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["space_pv_orchestration.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_routes={
        "space_pv.ingestion.*": {"queue": "ingestion"},
        "space_pv.orbit.*": {"queue": "orbit"},
        "space_pv.pv.*": {"queue": "pv"},
        "space_pv.analytics.*": {"queue": "analytics"},
    },
)
