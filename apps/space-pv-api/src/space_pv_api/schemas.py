from datetime import datetime
from typing import Any, Literal

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
    speed_m_s: float | None = None
    velocity_gcrs_m_s: tuple[float, float, float] | None = None
    illumination_fraction: float | None = None


class MapTrack(BaseModel):
    satellite_id: str
    name: str
    source: str
    samples: list[OrbitSample]
    norad_id: int | None = None
    element_epoch: datetime | None = None
    retrieved_at: datetime | None = None
    element_age_s: float | None = None
    source_sha256: str | None = None
    stale: bool = False
    position_kind: str = "visual_demo"


class MapScene(BaseModel):
    generated_at: datetime
    tracks: list[MapTrack]
    mode: Literal["live", "demo"] = "demo"
    warnings: list[str] = Field(default_factory=list)
    catalog_count: int = 0
    omitted_count: int = 0
    sample_interval_s: int = 30
