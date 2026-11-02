"""Live map boundary; external downloads are independent of render refreshes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from space_pv_connectors.celestrak import CelesTrakConnector
from space_pv_connectors.gp_cache import GPSnapshot, GPUnavailableError
from space_pv_orbit.astropy_engine import geocentric_sun_positions_m
from space_pv_orbit.tracking import omm_epoch, propagate_ground_track

from .config import APISettings
from .schemas import MapScene, MapTrack, OrbitSample

Group = Literal["stations", "starlink", "active", "weather", "gps-ops"]
router = APIRouter(prefix="/api/v1/map/live", tags=["live tracking"])


class LiveTrackingService:
    def __init__(self, cache_path: str | Path):
        self.cache_path = cache_path

    def snapshot(self, group: str, norad_id: int | None = None) -> GPSnapshot:
        with CelesTrakConnector() as connector:
            return connector.fetch_gp_cached(
                self.cache_path, catnr=norad_id, group=group if norad_id is None else None
            )

    @staticmethod
    def track(record, snapshot, times, now, sun) -> MapTrack:
        epoch = omm_epoch(record)
        age_s = (now - epoch).total_seconds()
        samples = propagate_ground_track(record, times, sun_positions_m=sun)
        norad_id = int(record["NORAD_CAT_ID"])
        return MapTrack(
            satellite_id=str(norad_id),
            norad_id=norad_id,
            name=str(record.get("OBJECT_NAME", norad_id)),
            source=snapshot.source,
            samples=[OrbitSample(**asdict(sample)) for sample in samples],
            element_epoch=epoch,
            retrieved_at=snapshot.retrieved_at,
            element_age_s=age_s,
            source_sha256=snapshot.sha256,
            stale=snapshot.cache_stale or abs(age_s) > 3 * 86400,
            position_kind="SGP4 prediction",
        )

    def scene(
        self, group: str, norad_id: int | None, limit: int, *, now: datetime | None = None
    ) -> MapScene:
        now = (now or datetime.now(UTC)).replace(microsecond=0)
        snapshot = self.snapshot(group, norad_id)
        # 3 minutes of five-second samples, interpolated by Cesium at wall time.
        times = [now + timedelta(seconds=offset) for offset in range(-5, 181, 5)]
        sun = geocentric_sun_positions_m(times)
        tracks, warnings = [], []
        if snapshot.warning:
            warnings.append(snapshot.warning)
        records = sorted(snapshot.records, key=lambda r: str(r.get("NORAD_CAT_ID", "")).zfill(9))
        for record in records:
            if len(tracks) >= limit:
                break
            try:
                tracks.append(self.track(record, snapshot, times, now, sun))
            except (ValueError, KeyError, TypeError, OverflowError):
                # Bad/old objects must not blank an otherwise usable constellation.
                continue
        omitted = len(records) - len(tracks)
        if omitted:
            warnings.append(
                f"{omitted} catalog objects omitted by the {limit}-object display limit, "
                "invalid elements or the 14-day element-age cutoff."
            )
        if any(track.stale for track in tracks):
            warnings.append("Some elements exceed 3 days or their download cache is overdue.")
        if not tracks:
            raise GPUnavailableError(
                "No usable orbital elements for this selection (14-day cutoff)"
            )
        return MapScene(
            generated_at=now,
            mode="live",
            tracks=tracks,
            warnings=warnings,
            catalog_count=len(records),
            omitted_count=omitted,
            sample_interval_s=5,
        )

    def selected_track(
        self, norad_id: int, group: str, individual: bool, *, now: datetime | None = None
    ) -> MapTrack:
        now = (now or datetime.now(UTC)).replace(microsecond=0)
        snapshot = self.snapshot(group, norad_id if individual else None)
        record = next(
            (r for r in snapshot.records if str(r.get("NORAD_CAT_ID")) == str(norad_id)), None
        )
        if record is None:
            raise LookupError("Satellite not present in the selected catalog snapshot")
        times = [now + timedelta(seconds=offset) for offset in range(-2700, 5401, 30)]
        return self.track(record, snapshot, times, now, geocentric_sun_positions_m(times))


service = LiveTrackingService(APISettings().gp_cache_path)


@router.get("", response_model=MapScene)
def live_scene(
    group: Group = "stations",
    norad_id: int | None = Query(default=None, ge=1, le=999999999),
    limit: int = Query(default=100, ge=1, le=100),
) -> MapScene:
    try:
        return service.scene(group, norad_id, limit)
    except GPUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/{norad_id}/track", response_model=MapTrack)
def live_track(
    norad_id: int,
    group: Group = "stations",
    individual: bool = False,
) -> MapTrack:
    if not 1 <= norad_id <= 999999999:
        raise HTTPException(status_code=422, detail="Invalid NORAD catalog ID")
    try:
        return service.selected_track(norad_id, group, individual)
    except GPUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=422, detail="Orbit cannot be propagated in this window"
        ) from None
