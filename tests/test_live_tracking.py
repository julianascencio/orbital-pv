from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import httpx
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from space_pv_api import tracking
from space_pv_connectors.celestrak import CelesTrakConnector
from space_pv_connectors.gp_cache import GPCache, GPSnapshot, GPUnavailableError
from space_pv_connectors.n2yo import N2YOConnector
from space_pv_orbit.tracking import omm_epoch, propagate_ground_track


@pytest.fixture
def omm():
    return json.loads((Path(__file__).parents[1] / "examples/data/iss_omm.json").read_text())


@pytest.fixture
def snapshot(omm):
    return GPSnapshot([omm], "CelesTrak", omm_epoch(omm), "a" * 64)


def test_cache_two_hour_ttl_survives_restart_and_empty_results(tmp_path):
    path = tmp_path / "gp.sqlite3"
    now = datetime(2026, 11, 2, tzinfo=UTC)
    loader = Mock(return_value=[])
    first = GPCache(path).get("CelesTrak", "stations", loader, now=now)
    second = GPCache(path).get("CelesTrak", "stations", loader, now=now + timedelta(seconds=7199))
    assert first == second
    assert loader.call_count == 1
    GPCache(path).get("CelesTrak", "stations", loader, now=now + timedelta(seconds=7200))
    assert loader.call_count == 2


def test_cache_serializes_concurrent_downloads(tmp_path):
    path = tmp_path / "gp.sqlite3"
    loader = Mock(return_value=[{"NORAD_CAT_ID": 100057}])
    with ThreadPoolExecutor(max_workers=4) as pool:
        snapshots = list(
            pool.map(lambda _: GPCache(path).get("CelesTrak", "stations", loader), range(4))
        )
    assert loader.call_count == 1
    assert len({s.sha256 for s in snapshots}) == 1


def test_cache_pauses_all_provider_queries_and_serves_labeled_old_snapshot(tmp_path, snapshot):
    cache = GPCache(tmp_path / "gp.sqlite3")
    now = snapshot.retrieved_at
    cache.get("CelesTrak", "stations", lambda: snapshot.records, now=now)
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(429, request=request)
    failed = Mock(side_effect=httpx.HTTPStatusError("limited", request=request, response=response))
    stale = cache.get("CelesTrak", "stations", failed, now=now + timedelta(hours=2))
    assert stale.cache_stale and stale.warning is not None
    assert "HTTP 429" in stale.warning
    assert stale.retrieved_at == now
    with pytest.raises(GPUnavailableError, match="paused"):
        cache.get("CelesTrak", "starlink", failed, now=now + timedelta(days=3))
    assert failed.call_count == 1
    cache.resume("CelesTrak")
    updated = cache.get(
        "CelesTrak", "stations", lambda: snapshot.records, now=now + timedelta(days=3)
    )
    assert not updated.cache_stale and updated.warning is None


def test_cache_detects_tampering(tmp_path):
    path = tmp_path / "gp.sqlite3"
    cache = GPCache(path)
    loader = Mock(return_value=[])
    cache.get("CelesTrak", "stations", loader)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE snapshots SET payload='[1]'")
    with pytest.raises(GPUnavailableError, match="checksum"):
        cache.get("CelesTrak", "stations", loader)
    assert loader.call_count == 1


def test_connector_requests_json_and_never_follows_redirect(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(301, headers={"Location": "https://example.test"})

    with CelesTrakConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(respond))
        for _ in range(2):
            with pytest.raises(GPUnavailableError, match="HTTP 301"):
                connector.fetch_gp_cached(tmp_path / "gp.sqlite3", catnr=100057)
    assert len(calls) == 1
    assert calls[0].url.params["FORMAT"] == "JSON"
    assert calls[0].url.params["CATNR"] == "100057"


def test_sgp4_wgs84_against_independent_astropy_transform(omm):
    from astropy import units as u
    from astropy.coordinates import ITRS, TEME, CartesianRepresentation, EarthLocation
    from astropy.time import Time
    from astropy.utils import iers
    from sgp4.api import Satrec
    from sgp4.omm import initialize

    times = [omm_epoch(omm) + timedelta(minutes=i) for i in range(0, 91, 10)]
    samples = propagate_ground_track(omm, times)
    satellite = Satrec()
    initialize(satellite, omm)
    at = Time(times)
    codes, position, _ = satellite.sgp4_array(at.jd1, at.jd2)
    assert not codes.any()
    with iers.conf.set_temp("auto_download", False):
        fixed = TEME(CartesianRepresentation(position.T * u.km), obstime=at).transform_to(
            ITRS(obstime=at)
        )
    reference = EarthLocation.from_geocentric(*fixed.cartesian.xyz).geodetic
    # Independent frame path: tolerate Earth-orientation table differences.
    np.testing.assert_allclose([s.latitude_deg for s in samples], reference.lat.deg, atol=0.001)
    np.testing.assert_allclose([s.longitude_deg for s in samples], reference.lon.deg, atol=0.005)
    np.testing.assert_allclose(
        [s.altitude_m for s in samples], reference.height.to_value(u.m), atol=30
    )
    assert all(400_000 < s.altitude_m < 440_000 for s in samples)
    assert all(7000 < s.speed_m_s < 8000 for s in samples)
    assert min(s.illumination_fraction for s in samples) == 0
    assert max(s.illumination_fraction for s in samples) == 1


def test_six_digit_ids_and_frame_contracts(omm):
    sample = propagate_ground_track({**omm, "NORAD_CAT_ID": 100057}, [omm_epoch(omm)])[0]
    assert np.isfinite(sample.altitude_m)
    for changes in ({"REF_FRAME": "GCRS"}, {"TIME_SYSTEM": "TAI"}, {"CENTER_NAME": "MARS"}):
        with pytest.raises(ValueError):
            propagate_ground_track({**omm, **changes}, [omm_epoch(omm)])


def test_tracking_refuses_old_future_naive_and_unsorted_times(omm):
    epoch = omm_epoch(omm)
    for times in (
        [epoch + timedelta(days=15)],
        [epoch - timedelta(days=15)],
        [epoch.replace(tzinfo=None)],
        [epoch, epoch],
        [epoch, epoch - timedelta(seconds=1)],
    ):
        with pytest.raises(ValueError):
            propagate_ground_track(omm, times)


def test_sgp4_error_is_rejected(omm):
    with pytest.raises(ValueError, match="SGP4"):
        propagate_ground_track({**omm, "MEAN_MOTION": 30}, [omm_epoch(omm)])


def test_scene_provenance_limit_and_selected_track_reuse(snapshot, monkeypatch, tmp_path):
    service = tracking.LiveTrackingService(tmp_path / "cache.sqlite3")
    get = Mock(return_value=replace(snapshot, records=[snapshot.records[0], {"NORAD_CAT_ID": 1}]))
    monkeypatch.setattr(service, "snapshot", get)
    scene = service.scene("stations", None, 1, now=snapshot.retrieved_at)
    assert scene.mode == "live" and scene.catalog_count == 2 and scene.omitted_count == 1
    assert scene.tracks[0].source_sha256 == snapshot.sha256
    assert scene.tracks[0].position_kind == "SGP4 prediction"
    assert len(scene.tracks[0].samples) == 38
    track = service.selected_track(25544, "stations", False, now=snapshot.retrieved_at)
    get.assert_called_with("stations", None)
    assert len(track.samples) == 271
    assert (track.samples[-1].timestamp - track.samples[0].timestamp).total_seconds() == 8100


def test_old_elements_not_relabelled_by_fresh_download(snapshot, monkeypatch, tmp_path):
    service = tracking.LiveTrackingService(tmp_path / "cache.sqlite3")
    now = snapshot.retrieved_at + timedelta(days=16)
    monkeypatch.setattr(service, "snapshot", lambda *args: replace(snapshot, retrieved_at=now))
    with pytest.raises(GPUnavailableError):
        service.scene("stations", None, 100, now=now)


def test_api_input_bounds_and_provider_outage(monkeypatch):
    app = FastAPI()
    app.include_router(tracking.router)
    client = TestClient(app)
    for query in ("limit=101", "limit=0", "norad_id=0", "norad_id=1000000000", "group=../../"):
        assert client.get(f"/api/v1/map/live?{query}").status_code == 422
    monkeypatch.setattr(
        tracking.service, "scene", Mock(side_effect=GPUnavailableError("Provider paused"))
    )
    response = client.get("/api/v1/map/live")
    assert response.status_code == 503
    assert "demo" not in response.text.lower()


def test_n2yo_credentials_validation_and_no_key_in_errors():
    with N2YOConnector(api_key="private-test-key") as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(403))
        )
        with pytest.raises(ValueError):
            connector.positions(25544, observer_lat=91, observer_lon=0)
        with pytest.raises(ValueError):
            connector.positions(25544, observer_lat=0, observer_lon=0, seconds=301)
        with pytest.raises(RuntimeError) as exc:
            connector.positions(25544, observer_lat=0, observer_lon=0)
        assert "private-test-key" not in str(exc.value)


def test_n2yo_preserves_units_and_unknown_epoch():
    def respond(request):
        return httpx.Response(
            200,
            json={"info": {"satid": 100057}, "positions": [{"sataltitude": 420, "timestamp": 123}]},
        )

    with N2YOConnector(api_key="test") as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(respond))
        result = connector.positions(100057, observer_lat=28.4, observer_lon=-16.3)
    assert result["element_epoch"] is None
    assert result["sataltitude_unit"] == "km"
    assert result["position_kind"] == "predicted"


def test_spacetrack_current_omm_reuses_snapshot_after_new_connector(tmp_path, omm):
    from space_pv_connectors.space_track import SpaceTrackConnector

    path = tmp_path / "gp.sqlite3"
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[omm])

    for _ in range(2):
        with SpaceTrackConnector() as connector:
            connector._client.close()
            connector._client = httpx.Client(transport=httpx.MockTransport(respond))
            snapshot = connector.latest_gp_cached(25544, cache_path=path)
            assert snapshot.source == "Space-Track"
            assert snapshot.records[0]["EPOCH"] == omm["EPOCH"]
    assert len(requests) == 1


def test_public_fetch_does_not_silently_return_stale_snapshot(snapshot, monkeypatch):
    import orbitalpv as opv

    monkeypatch.setattr(
        CelesTrakConnector,
        "fetch_gp_cached",
        lambda *args, **kwargs: replace(snapshot, cache_stale=True),
    )
    with pytest.raises(GPUnavailableError, match="overdue"):
        opv.fetch_celestrak_omm(25544)
