from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from space_pv_connectors.ground_osm import OpenStreetMapEnergyConnector

BBOX = (-0.82, 44.70, -0.72, 44.76)


def _payload() -> dict:
    """Offline source-schema fixture, not a claimed real OSM installation."""
    outer = [
        {"lat": 44.72, "lon": -0.78},
        {"lat": 44.74, "lon": -0.78},
        {"lat": 44.74, "lon": -0.76},
        {"lat": 44.72, "lon": -0.78},
    ]
    return {
        "version": 0.6,
        "generator": "Overpass API fixture",
        "osm3s": {
            "timestamp_osm_base": "2025-08-15T12:00:00Z",
            "copyright": "The data included in this document is from www.openstreetmap.org.",
        },
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 44.73,
                "lon": -0.79,
                # Deliberately no power tag: the paper selects by source tag.
                "tags": {"generator:source": "wind", "generator:output:electricity": "yes"},
            },
            {
                "type": "way",
                "id": 2,
                "nodes": [11, 12, 13, 11],
                "geometry": outer,
                "tags": {
                    "power": "generator",
                    "generator:source": "solar",
                    "generator:method": "photovoltaic",
                },
            },
            {
                "type": "relation",
                "id": 3,
                "members": [
                    {"type": "way", "ref": 2, "role": "outer", "geometry": outer},
                    {
                        "type": "way",
                        "ref": 4,
                        "role": "inner",
                        "geometry": [
                            {"lat": 44.73, "lon": -0.775},
                            {"lat": 44.731, "lon": -0.775},
                            {"lat": 44.731, "lon": -0.774},
                            {"lat": 44.73, "lon": -0.775},
                        ],
                    },
                    {"type": "relation", "ref": 8, "role": "subarea"},
                ],
                "tags": {"type": "multipolygon", "plant:source": "solar"},
            },
        ],
    }


def _connector(
    response: dict | Callable[[httpx.Request], httpx.Response],
    requests: list[httpx.Request] | None = None,
) -> OpenStreetMapEnergyConnector:
    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        if isinstance(response, dict):
            return httpx.Response(200, json=response)
        return response(request)

    connector = OpenStreetMapEnergyConnector()
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(respond))
    return connector


def test_query_reorders_bbox_and_selects_source_tags_without_requiring_power() -> None:
    requests: list[httpx.Request] = []
    with _connector(_payload(), requests) as connector:
        result = connector.fetch_energy_features(bbox=BBOX)

    assert result == _payload()
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://overpass-api.de/api/interpreter"
    query = parse_qs(request.content.decode())["data"][0]
    for source in ("solar", "wind"):
        assert f'nwr["generator:source"="{source}"](44.7,-0.82,44.76,-0.72);' in query
        assert f'nwr["plant:source"="{source}"](44.7,-0.82,44.76,-0.72);' in query
        assert f'["power"~"^(generator|plant)$"]["power_source"="{source}"]' in query
    assert query.endswith("out body geom;")
    assert "out center" not in query
    assert "out body geom(" not in query  # Keep complete rings outside the selection box.


def test_raw_geometry_roles_unknown_tags_and_source_timestamp_are_preserved() -> None:
    payload = _payload()
    payload["elements"][1]["tags"]["custom:survey"] = "retain verbatim"
    with _connector(payload) as connector:
        result = connector.fetch_energy_features(bbox=BBOX)

    assert result == payload
    assert result["elements"][1]["nodes"] == [11, 12, 13, 11]
    members = result["elements"][2]["members"]
    assert [member["role"] for member in members] == ["outer", "inner", "subarea"]
    assert members[2] == {"type": "relation", "ref": 8, "role": "subarea"}


def test_cache_is_offline_query_bound_and_checksummed(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    path = tmp_path / "osm.json"
    with _connector(_payload(), requests) as connector:
        result = connector.fetch_energy_features(bbox=BBOX, cache_path=path)
        cached = connector.fetch_energy_features(
            bbox=BBOX, sources=("wind", "solar", "solar"), cache_path=path
        )
        assert cached == result
        assert len(requests) == 1
        meta = json.loads(path.with_suffix(".json.meta.json").read_text())
        assert meta["sha256"] == sha256(path.read_bytes()).hexdigest()
        assert meta["request"]["bbox"] == list(BBOX)
        assert meta["license"] == "ODbL-1.0"
        assert meta["attribution"] == "© OpenStreetMap contributors"
        assert meta["retrieved_at"]
        assert json.loads(path.read_text()) == result
        with pytest.raises(ValueError, match="different query"):
            connector.fetch_energy_features(bbox=BBOX, sources=("solar",), cache_path=path)
        with pytest.raises(ValueError, match="different query"):
            connector.fetch_energy_features(bbox=(-0.81, 44.70, -0.72, 44.76), cache_path=path)
        path.write_text("{}")
        with pytest.raises(ValueError, match="SHA-256"):
            connector.fetch_energy_features(bbox=BBOX, cache_path=path)
        assert len(requests) == 1


def test_refresh_updates_snapshot_and_can_replace_an_unverified_cache(tmp_path: Path) -> None:
    path = tmp_path / "osm.json"
    path.write_text("old data without provenance")
    requests: list[httpx.Request] = []
    with _connector(_payload(), requests) as connector:
        with pytest.raises(ValueError, match="no provenance"):
            connector.fetch_energy_features(bbox=BBOX, cache_path=path)
        refreshed = connector.fetch_energy_features(bbox=BBOX, cache_path=path, refresh=True)
        assert json.loads(path.read_text()) == refreshed
        assert len(requests) == 1


@pytest.mark.parametrize("status", [429, 503])
def test_http_errors_do_not_create_cache(status: int, tmp_path: Path) -> None:
    path = tmp_path / "unavailable.json"
    with (
        _connector(lambda request: httpx.Response(status, text="Unavailable")) as connector,
        pytest.raises(httpx.HTTPStatusError),
    ):
        connector.fetch_energy_features(bbox=BBOX, cache_path=path)
    assert not path.exists()
    assert not path.with_suffix(".json.meta.json").exists()


def test_partial_overpass_response_raises_and_does_not_replace_good_cache(tmp_path: Path) -> None:
    path = tmp_path / "osm.json"
    with _connector(_payload()) as connector:
        connector.fetch_energy_features(bbox=BBOX, cache_path=path)
    original = path.read_bytes()
    metadata = path.with_suffix(".json.meta.json").read_bytes()
    partial = deepcopy(_payload())
    partial["remark"] = "runtime error: Query timed out"
    with _connector(partial) as connector, pytest.raises(RuntimeError, match="incomplete"):
        connector.fetch_energy_features(bbox=BBOX, cache_path=path, refresh=True)
    assert path.read_bytes() == original
    assert path.with_suffix(".json.meta.json").read_bytes() == metadata


def test_empty_result_remains_a_valid_empty_dataset() -> None:
    payload = _payload()
    payload["elements"] = []
    with _connector(payload) as connector:
        assert connector.fetch_energy_features(bbox=BBOX) == payload


@pytest.mark.parametrize(
    "bbox",
    [
        (0, 0, 1),
        (0, 0, 1, float("nan")),
        (0, 0, float("inf"), 1),
        (-181, 0, -179, 0.1),
        (0, -91, 0.1, -89),
        (170, 0, -170, 0.1),
        (0, 1, 0.1, 1),
        (0, 0, 2, 2),
        (False, 0, 1, 1),
    ],
)
def test_invalid_regions_fail_before_network(bbox: tuple) -> None:
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError):
        connector.fetch_energy_features(bbox=bbox)
    assert not requests


@pytest.mark.parametrize("sources", [(), ("coal",), ("Solar",), "solar", ('solar"];out;',)])
def test_invalid_sources_fail_before_network(sources) -> None:
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError, match="sources"):
        connector.fetch_energy_features(bbox=BBOX, sources=sources)
    assert not requests


@pytest.mark.parametrize(
    "payload",
    [{}, {"elements": {}}, {"elements": [None]}, {"elements": [{"type": "way", "id": "2"}]}],
)
def test_malformed_source_schema_does_not_create_cache(payload: dict, tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    with _connector(payload) as connector, pytest.raises(ValueError):
        connector.fetch_energy_features(bbox=BBOX, cache_path=path)
    assert not path.exists()


def test_non_json_response_does_not_create_cache(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    with (
        _connector(
            lambda request: httpx.Response(200, text="<html>unavailable</html>")
        ) as connector,
        pytest.raises(ValueError, match="JSON"),
    ):
        connector.fetch_energy_features(bbox=BBOX, cache_path=path)
    assert not path.exists()
