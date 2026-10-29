from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SatelliteIdentity:
    name: str
    norad_id: int | None = None
    cospar_id: str | None = None
    satnogs_id: str | None = None


@dataclass(frozen=True, slots=True)
class OrbitState:
    timestamp: datetime
    position_m: tuple[float, float, float]
    velocity_m_s: tuple[float, float, float] | None
    frame: str
    source: str


@dataclass(frozen=True, slots=True)
class AttitudeState:
    timestamp: datetime
    quaternion_wxyz: tuple[float, float, float, float]
    body_frame: str
    reference_frame: str
    source: str


@dataclass(frozen=True, slots=True)
class PanelTelemetry:
    timestamp: datetime
    panel_id: str
    voltage_v: float
    current_a: float
    temperature_c: float | None = None

    @property
    def power_w(self) -> float:
        return self.voltage_v * self.current_a


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source: str
    retrieval_timestamp: datetime
    request: str
    sha256: str | None = None
    license_or_terms: str | None = None


@dataclass(frozen=True, slots=True)
class DegradationEstimate:
    slope_per_day: float
    slope_percent_per_year: float
    intercept: float
    n_samples: int


@dataclass(frozen=True, slots=True)
class Case0Summary:
    n_samples: int
    n_panels: int
    anomaly_day_fraction: float
    degradation: DegradationEstimate
    persistent_loss_detected: bool
    persistent_loss_start: str | None
    persistent_loss_fraction: float | None
