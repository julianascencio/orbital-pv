from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .postgres import JobRun, JobStatus


def create_job(session: Session, task_name: str, payload: dict[str, Any]) -> JobRun:
    job = JobRun(task_name=task_name, payload=payload, status=JobStatus.QUEUED)
    session.add(job); session.commit(); session.refresh(job); return job


def attach_celery_task(session: Session, job: JobRun, celery_task_id: str) -> JobRun:
    job.celery_task_id = celery_task_id; session.commit(); session.refresh(job); return job


def mark_running(session: Session, job_id: str) -> JobRun | None:
    job = session.get(JobRun, job_id)
    if job is None: return None
    job.status = JobStatus.RUNNING; job.started_at = datetime.now(UTC); session.commit(); return job


def mark_succeeded(session: Session, job_id: str, result: dict[str, Any]) -> JobRun | None:
    job = session.get(JobRun, job_id)
    if job is None: return None
    job.status = JobStatus.SUCCEEDED; job.result = result; job.finished_at = datetime.now(UTC); session.commit(); return job


def mark_failed(session: Session, job_id: str, error: str) -> JobRun | None:
    job = session.get(JobRun, job_id)
    if job is None: return None
    job.status = JobStatus.FAILED; job.error = error; job.finished_at = datetime.now(UTC); session.commit(); return job


def list_jobs(session: Session, limit: int = 100) -> list[JobRun]:
    statement = select(JobRun).order_by(JobRun.created_at.desc()).limit(limit)
    return list(session.scalars(statement))
