"""Persistence adapters for analytical and operational Space PV data."""

from .config import StorageSettings
from .duckdb_store import DuckDBStore
from .jobs import attach_celery_task, create_job, list_jobs, mark_failed, mark_running, mark_succeeded
from .map_store import (
    get_track_samples,
    list_latest_satellite_states,
    upsert_latest_satellite_state,
    upsert_satellite_catalog,
    write_track_segment,
)
from .postgres import Base, JobRun, JobStatus, create_engine_from_settings, session_factory

__all__ = [
    "Base",
    "DuckDBStore",
    "JobRun",
    "JobStatus",
    "StorageSettings",
    "attach_celery_task",
    "create_engine_from_settings",
    "create_job",
    "list_jobs",
    "list_latest_satellite_states",
    "get_track_samples",
    "mark_failed",
    "mark_running",
    "mark_succeeded",
    "session_factory",
    "upsert_latest_satellite_state",
    "upsert_satellite_catalog",
    "write_track_segment",
]
