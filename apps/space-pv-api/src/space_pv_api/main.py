from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from space_pv_orchestration.celery_app import celery_app
from space_pv_storage import (
    Base,
    JobRun,
    attach_celery_task,
    create_engine_from_settings,
    create_job,
    list_jobs,
    list_latest_satellite_states,
    get_track_samples,
    session_factory,
)

from .config import APISettings
from .schemas import JobAccepted, JobCreate, JobRead, MapSatelliteState, MapScene, MapTrack, OrbitSample

settings = APISettings()
engine = create_engine_from_settings()
SessionLocal = session_factory()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Development bootstrap. Replace with Alembic migrations before production.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Space PV Analytics API",
    version="0.1.0",
    description="API for satellite ingestion, orbit/PV computations and analytics jobs.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "space-pv-api"}


@app.post("/api/v1/jobs", response_model=JobAccepted, status_code=202)
def submit_job(request: JobCreate) -> JobAccepted:
    with SessionLocal() as session:
        job = create_job(session, request.job_type, request.payload)
        task = celery_app.send_task(
            "space_pv.analytics.execute",
            args=[job.id, request.job_type, request.payload],
            queue="analytics",
        )
        attach_celery_task(session, job, task.id)
        return JobAccepted(job_id=job.id, task_id=task.id, job_type=request.job_type)


def _job_to_schema(job: JobRun) -> JobRead:
    return JobRead(
        id=job.id,
        task_name=job.task_name,
        celery_task_id=job.celery_task_id,
        status=job.status.value,
        payload=job.payload,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@app.get("/api/v1/jobs", response_model=list[JobRead])
def jobs(limit: int = 100) -> list[JobRead]:
    with SessionLocal() as session:
        return [_job_to_schema(job) for job in list_jobs(session, min(max(limit, 1), 500))]


@app.get("/api/v1/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str) -> JobRead:
    with SessionLocal() as session:
        job = session.get(JobRun, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_to_schema(job)



@app.get("/api/v1/map/satellites/latest", response_model=list[MapSatelliteState])
def latest_satellite_map_states(limit: int = 2000) -> list[MapSatelliteState]:
    with SessionLocal() as session:
        rows = list_latest_satellite_states(session, min(max(limit, 1), 10000))
    return [MapSatelliteState(**row) for row in rows]


@app.get("/api/v1/map/satellites/{satellite_id}/track", response_model=MapTrack)
def satellite_track(
    satellite_id: str,
    start: datetime,
    end: datetime,
    lod: int = 1,
) -> MapTrack:
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    with SessionLocal() as session:
        segments = get_track_samples(session, satellite_id, start, end, lod)
    if not segments:
        raise HTTPException(status_code=404, detail="No cached track for requested window")

    samples: list[OrbitSample] = []
    for segment in segments:
        epoch = segment["start_at"]
        for offset_s, lon, lat, altitude_m in segment["samples"]:
            timestamp = epoch + timedelta(seconds=float(offset_s))
            if start <= timestamp <= end:
                samples.append(
                    OrbitSample(
                        timestamp=timestamp,
                        longitude_deg=float(lon),
                        latitude_deg=float(lat),
                        altitude_m=float(altitude_m),
                    )
                )
    return MapTrack(
        satellite_id=satellite_id,
        name=satellite_id,
        source=str(segments[0]["source"]),
        samples=samples,
    )


def _demo_track(
    name: str,
    inclination_deg: float,
    altitude_m: float,
    phase_deg: float,
    epoch: datetime,
) -> MapTrack:
    """Visual-only deterministic samples used to validate the Cesium pipeline.

    These are deliberately not presented as propagated ephemerides. Real tracks come
    from space-pv-orbit and are cached in gis.orbit_track_segments.
    """
    period_s = 95.0 * 60.0
    samples: list[OrbitSample] = []
    for offset_s in range(0, 2 * 60 * 60 + 1, 30):
        theta = 2.0 * math.pi * offset_s / period_s + math.radians(phase_deg)
        latitude = inclination_deg * math.sin(theta)
        longitude = ((math.degrees(theta) * 0.78 + phase_deg + 180.0) % 360.0) - 180.0
        samples.append(
            OrbitSample(
                timestamp=epoch + timedelta(seconds=offset_s),
                longitude_deg=longitude,
                latitude_deg=latitude,
                altitude_m=altitude_m,
            )
        )
    return MapTrack(satellite_id=name.lower().replace(" ", "-"), name=name, source="visual_demo", samples=samples)


@app.get("/api/v1/map/demo", response_model=MapScene)
def demo_map_scene() -> MapScene:
    epoch = datetime.now(UTC).replace(microsecond=0)
    return MapScene(
        generated_at=epoch,
        tracks=[
            _demo_track("Demo LEO 51.6", 51.6, 420_000.0, 0.0, epoch),
            _demo_track("Demo SSO 97.4", 82.0, 550_000.0, 115.0, epoch),
            _demo_track("Demo LEO 35", 35.0, 650_000.0, 235.0, epoch),
        ],
    )


def run() -> None:
    import uvicorn

    uvicorn.run("space_pv_api.main:app", host=settings.api_host, port=settings.api_port, reload=False)
