from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class JobAccepted(BaseModel):
    job_id: str
    task_id: str
    job_type: str
    status: str = "queued"


class JobRead(BaseModel):
    id: str
    task_name: str
    celery_task_id: str | None
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MapSatelliteState(BaseModel):
    satellite_id: str
    name: str
    norad_id: int | None = None
    observed_at: datetime
    longitude_deg: float
    latitude_deg: float
    altitude_m: float
    illumination_fraction: float | None = None
    pv_power_w: float | None = None
    source: str


class OrbitSample(BaseModel):
    timestamp: datetime
    longitude_deg: float
    latitude_deg: float
    altitude_m: float


class MapTrack(BaseModel):
    satellite_id: str
    name: str
    source: str
    samples: list[OrbitSample]


class MapScene(BaseModel):
    generated_at: datetime
    tracks: list[MapTrack]
