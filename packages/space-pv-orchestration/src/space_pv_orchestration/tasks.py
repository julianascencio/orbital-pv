from datetime import UTC, datetime
from typing import Any
from space_pv_storage import mark_failed, mark_running, mark_succeeded, session_factory
from .celery_app import celery_app
SessionLocal = session_factory()

@celery_app.task(name="space_pv.system.ping")
def ping() -> dict[str,str]: return {"status":"ok","timestamp":datetime.now(UTC).isoformat()}

@celery_app.task(name="space_pv.analytics.execute", bind=True)
def execute_analysis(self, job_id: str, job_type: str, payload: dict[str,Any]) -> dict[str,Any]:
    with SessionLocal() as session: mark_running(session, job_id)
    try:
        result={"job_id":job_id,"job_type":job_type,"payload":payload,"status":"completed","celery_task_id":self.request.id,"executed_at":datetime.now(UTC).isoformat()}
        with SessionLocal() as session: mark_succeeded(session,job_id,result)
        return result
    except Exception as exc:
        with SessionLocal() as session: mark_failed(session,job_id,str(exc))
        raise
