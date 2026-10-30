from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import pytest

from space_pv_connectors.ground_imagery import Sentinel2GroundConnector

BBOX = (-0.82, 44.70, -0.72, 44.76)
SEARCH = {"bbox": BBOX, "time_min": "2024-06-01", "time_max": "2024-07-01"}


def _item(identifier: str = "S2_fixture_1") -> dict[str, Any]:
    """Explicit offline STAC-schema fixture, not a real measured scene."""
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": identifier,
        "collection": "sentinel-2-c1-l2a",
        "bbox": list(BBOX),
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-0.82, 44.70], [-0.82, 44.76], [-0.72, 44.76], [-0.82, 44.70]]],
        },
        "properties": {
            "datetime": "2024-06-15T10:35:00Z",
            "eo:cloud_cover": 4.5,
            "platform": "sentinel-2b",
            "s2:processing_baseline": "05.00",
        },
        "assets": {
            "red": {
                "href": "https://example.com/sentinel/B04.tif",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "gsd": 10,
                "raster:bands": [{"scale": 0.0001, "offset": -0.1, "nodata": 0}],
            },
            "scl": {
                "href": "https://example.com/sentinel/SCL.tif",
                "gsd": 20,
                "raster:bands": [{"nodata": 0}],
            },
        },
        "links": [{"rel": "license", "href": "https://example.com/license"}],
    }


def _page(
    identifiers: tuple[str, ...] = ("S2_fixture_1",),
    *,
    links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [_item(identifier) for identifier in identifiers],
        "links": [] if links is None else links,
    }


def _connector(
    response: dict[str, Any] | Callable[[httpx.Request], httpx.Response],
    requests: list[httpx.Request] | None = None,
) -> Sentinel2GroundConnector:
    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        if isinstance(response, dict):
            return httpx.Response(200, json=response)
        return response(request)

    connector = Sentinel2GroundConnector()
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(respond))
    return connector


class _Chunks(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes], *, fail: bool = False) -> None:
        self.chunks = chunks
        self.fail = fail
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield from self.chunks
        if self.fail:
            raise httpx.ReadError("Interrupted asset stream")

    def close(self) -> None:
        self.closed = True


def test_search_requests_collection_bbox_utc_cloud_filter_and_sort() -> None:
    requests: list[httpx.Request] = []
    with _connector(_page(), requests) as connector:
        result = connector.search(
            bbox=BBOX,
            time_min="2024-06-01T01:00:00+01:00",
            time_max="2024-07-01",
            max_cloud_cover=12.5,
            max_items=200,
        )
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://earth-search.aws.element84.com/v1/search"
    assert json.loads(request.content) == {
        "collections": ["sentinel-2-c1-l2a"],
        "bbox": list(BBOX),
        "datetime": "2024-06-01T00:00:00+00:00/2024-07-01T00:00:00+00:00",
        "limit": 100,
        "query": {"eo:cloud_cover": {"lte": 12.5}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    assert result["features"] == [_item()]
    assert result["context"] == {
        "returned": 1,
        "matched": None,
        "limit": 200,
        "limit_reached": False,
    }


@pytest.mark.parametrize("merge", [False, True])
def test_post_pagination_respects_complete_body_and_explicit_merge(merge: bool) -> None:
    requests: list[httpx.Request] = []
    next_body = {"next": "opaque-token", "limit": 2}

    def respond(request: httpx.Request) -> httpx.Response:
        if len(requests) == 1:
            return httpx.Response(
                200,
                json=_page(
                    links=[
                        {
                            "rel": "next",
                            "href": "/v1/search",
                            "method": "POST",
                            "body": next_body,
                            "merge": merge,
                        }
                    ]
                ),
            )
        return httpx.Response(200, json=_page(("S2_fixture_2",)))

    with _connector(respond, requests) as connector:
        result = connector.search(**SEARCH)
    initial = json.loads(requests[0].content)
    assert len(requests) == 2
    assert requests[1].method == "POST"
    expected = {**initial, **next_body} if merge else next_body
    assert json.loads(requests[1].content) == expected
    assert [item["id"] for item in result["features"]] == ["S2_fixture_1", "S2_fixture_2"]


def test_get_pagination_keeps_query_string_and_sends_no_request_body() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if len(requests) == 1:
            return httpx.Response(
                200,
                json=_page(
                    links=[
                        {
                            "rel": "next",
                            "href": "?token=page%3A2",
                            "method": "GET",
                        }
                    ]
                ),
            )
        return httpx.Response(200, json=_page(("S2_fixture_2",)))

    with _connector(respond, requests) as connector:
        result = connector.search(**SEARCH)
    assert len(result["features"]) == 2
    assert requests[1].method == "GET"
    assert str(requests[1].url).endswith("/v1/search?token=page%3A2")
    assert not requests[1].content


def test_duplicates_do_not_consume_cap_and_cap_is_explicit() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if len(requests) == 1:
            page = _page(
                ("one", "one"),
                links=[
                    {
                        "rel": "next",
                        "href": "?token=2",
                        "method": "GET",
                    }
                ],
            )
            page["context"] = {"matched": 50}
        else:
            page = _page(
                ("one", "two", "three", "four"),
                links=[
                    {
                        "rel": "next",
                        "href": "?token=3",
                        "method": "GET",
                    }
                ],
            )
        return httpx.Response(200, json=page)

    with _connector(respond, requests) as connector:
        result = connector.search(**SEARCH, max_items=3)
    assert len(requests) == 2
    assert [item["id"] for item in result["features"]] == ["one", "two", "three"]
    assert result["context"] == {
        "returned": 3,
        "matched": 50,
        "limit": 3,
        "limit_reached": True,
    }


def test_pagination_cycle_is_rejected_without_an_unbounded_request_loop() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_page(
                links=[
                    {
                        "rel": "next",
                        "href": str(request.url),
                        "method": "POST",
                        "body": json.loads(request.content),
                    }
                ]
            ),
        )

    with (
        _connector(respond, requests) as connector,
        pytest.raises(ValueError, match="pagination repeated"),
    ):
        connector.search(**SEARCH)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "link",
    [
        {"rel": "next", "href": "https://different.example/search"},
        {"rel": "next", "href": "http://earth-search.aws.element84.com/v1/search"},
        {"rel": "next", "href": "?next=2", "method": "DELETE"},
        {"rel": "next", "href": "?next=2", "method": "GET", "body": {"next": 2}},
        {"rel": "next", "href": "?next=2", "method": "POST", "body": []},
        {"rel": "next"},
    ],
)
def test_invalid_pagination_is_rejected_before_a_second_request(link: dict[str, Any]) -> None:
    requests: list[httpx.Request] = []
    with _connector(_page(links=[link]), requests) as connector, pytest.raises(ValueError):
        connector.search(**SEARCH)
    assert len(requests) == 1


def test_assets_native_resolution_calibration_quality_and_metadata_are_unchanged() -> None:
    page = _page()
    page["features"][0]["properties"]["provider:extra"] = {"quality": "retain verbatim"}
    with _connector(page) as connector:
        result = connector.search(**SEARCH)
    assert result["features"] == page["features"]
    assets = result["features"][0]["assets"]
    assert assets["red"]["raster:bands"][0] == {"scale": 0.0001, "offset": -0.1, "nodata": 0}
    assert assets["scl"]["gsd"] == 20


def test_empty_search_returns_empty_feature_collection() -> None:
    page = _page(())
    page["numberMatched"] = 0
    with _connector(page) as connector:
        result = connector.search(**SEARCH)
    assert result["type"] == "FeatureCollection"
    assert result["features"] == []
    assert result["context"] == {
        "returned": 0,
        "matched": 0,
        "limit": 20,
        "limit_reached": False,
    }


def test_search_cache_reuses_offline_and_records_request_page_and_snapshot_checksums(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []
    path = tmp_path / "scenes.json"
    with _connector(_page(), requests) as connector:
        first = connector.search(**SEARCH, cache_path=path)
        assert connector.search(**SEARCH, cache_path=path) == first
    assert len(requests) == 1
    sidecar = json.loads(path.with_suffix(".json.meta.json").read_text())
    assert sidecar["sha256"] == sha256(path.read_bytes()).hexdigest()
    assert sidecar["request"]["search"]["bbox"] == list(BBOX)
    assert sidecar["request"]["max_items"] == 20
    assert len(sidecar["pages"]) == 1
    assert sidecar["pages"][0]["sha256"]
    assert sidecar["pages"][0]["retrieved_at"]
    assert json.loads(path.read_text()) == first


def test_search_cache_query_mismatch_and_tampering_raise_before_http(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    path = tmp_path / "scenes.json"
    with _connector(_page(), requests) as connector:
        connector.search(**SEARCH, cache_path=path)
        with pytest.raises(ValueError, match="different query"):
            connector.search(**SEARCH, max_cloud_cover=5, cache_path=path)
        with pytest.raises(ValueError, match="different query"):
            connector.search(**SEARCH, max_items=21, cache_path=path)
        path.write_text("{}")
        with pytest.raises(ValueError, match="SHA-256"):
            connector.search(**SEARCH, cache_path=path)
    assert len(requests) == 1


def test_refresh_can_replace_unverified_cache_with_new_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "scenes.json"
    path.write_text("old snapshot without provenance")
    requests: list[httpx.Request] = []
    with _connector(_page(), requests) as connector:
        with pytest.raises(ValueError, match="no provenance"):
            connector.search(**SEARCH, cache_path=path)
        result = connector.search(**SEARCH, cache_path=path, refresh=True)
    assert len(requests) == 1
    assert json.loads(path.read_text()) == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("bbox", (0, 0, 1)),
        ("bbox", (0, 0, float("nan"), 1)),
        ("bbox", (0, 0, float("inf"), 1)),
        ("bbox", (-181, 0, -179, 1)),
        ("bbox", (0, -91, 1, -89)),
        ("bbox", (170, 0, -170, 1)),
        ("bbox", (0, 0, 1, 0)),
        ("bbox", (False, 0, 1, 1)),
        ("time_min", "NaT"),
        ("time_min", "not-a-time"),
        ("time_max", "2024-05-01"),
        ("max_cloud_cover", -1),
        ("max_cloud_cover", 101),
        ("max_cloud_cover", float("nan")),
        ("max_cloud_cover", True),
        ("max_items", 0),
        ("max_items", 10001),
        ("max_items", True),
        ("max_items", 1.5),
    ],
)
def test_invalid_search_inputs_raise_before_http(field: str, value: Any) -> None:
    arguments = {**SEARCH, field: value}
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError):
        connector.search(**arguments)
    assert not requests


@pytest.mark.parametrize("status", [429, 503])
def test_search_http_failure_does_not_create_a_cache(status: int, tmp_path: Path) -> None:
    path = tmp_path / "unavailable.json"
    with (
        _connector(lambda request: httpx.Response(status)) as connector,
        pytest.raises(httpx.HTTPStatusError),
    ):
        connector.search(**SEARCH, cache_path=path)
    assert not path.exists()
    assert not path.with_suffix(".json.meta.json").exists()


def test_failed_refresh_preserves_existing_search_cache(tmp_path: Path) -> None:
    path = tmp_path / "scenes.json"
    with _connector(_page()) as connector:
        connector.search(**SEARCH, cache_path=path)
    original = path.read_bytes()
    metadata = path.with_suffix(".json.meta.json").read_bytes()
    with (
        _connector(lambda request: httpx.Response(503)) as connector,
        pytest.raises(httpx.HTTPStatusError),
    ):
        connector.search(**SEARCH, cache_path=path, refresh=True)
    assert path.read_bytes() == original
    assert path.with_suffix(".json.meta.json").read_bytes() == metadata


def test_invalid_stac_item_does_not_create_a_cache(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    page = _page()
    page["features"][0].pop("assets")
    with _connector(page) as connector, pytest.raises(ValueError, match="Invalid STAC item"):
        connector.search(**SEARCH, cache_path=path)
    assert not path.exists()


def test_asset_stream_is_saved_with_exact_checksum_and_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "red.tif"
    stream = _Chunks([b"first-", b"second-", b"third"])
    requests: list[httpx.Request] = []
    with _connector(lambda request: httpx.Response(200, stream=stream), requests) as connector:
        receipt = connector.download_asset(_item(), "red", path, max_bytes=100)
    expected = b"first-second-third"
    assert path.read_bytes() == expected
    assert receipt.sha256 == sha256(expected).hexdigest()
    assert receipt.bytes == len(expected)
    assert receipt.path == str(path)
    assert receipt.url == "https://example.com/sentinel/B04.tif"
    assert stream.closed
    assert requests[0].method == "GET"
    provenance = json.loads(path.with_suffix(".tif.meta.json").read_text())
    assert provenance["sha256"] == receipt.sha256
    assert provenance["asset_key"] == "red"
    assert provenance["item"] == _item()


@pytest.mark.parametrize("announced", [True, False])
def test_asset_size_limit_applies_to_announced_and_streamed_bytes(
    announced: bool, tmp_path: Path
) -> None:
    path = tmp_path / "too-large.tif"
    stream = _Chunks([b"1234", b"5678", b"9"])
    headers = {"Content-Length": "9"} if announced else {}
    with (
        _connector(
            lambda request: httpx.Response(200, headers=headers, stream=stream)
        ) as connector,
        pytest.raises(ValueError, match="max_bytes"),
    ):
        connector.download_asset(_item(), "red", path, max_bytes=8)
    assert stream.closed
    assert not path.exists()
    assert not path.with_suffix(".tif.meta.json").exists()
    assert list(tmp_path.iterdir()) == []  # No leaked partial download.


def test_empty_asset_is_not_accepted_as_a_successful_download(tmp_path: Path) -> None:
    path = tmp_path / "empty.tif"
    with (
        _connector(lambda request: httpx.Response(200, stream=_Chunks([]))) as connector,
        pytest.raises(ValueError, match="empty"),
    ):
        connector.download_asset(_item(), "red", path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["http", "stream", "size"])
def test_failed_asset_download_preserves_existing_destination_and_sidecar(
    failure: str, tmp_path: Path
) -> None:
    path = tmp_path / "red.tif"
    sidecar = path.with_suffix(".tif.meta.json")
    path.write_bytes(b"existing asset")
    sidecar.write_bytes(b"existing metadata")

    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "http":
            return httpx.Response(503)
        return httpx.Response(
            200, stream=_Chunks([b"partial", b"overflow"], fail=failure == "stream")
        )

    expected_error = {
        "http": httpx.HTTPStatusError,
        "stream": httpx.ReadError,
        "size": ValueError,
    }[failure]
    with _connector(respond) as connector, pytest.raises(expected_error):
        connector.download_asset(
            _item(), "red", path, max_bytes=8 if failure == "size" else 100, overwrite=True
        )
    assert path.read_bytes() == b"existing asset"
    assert sidecar.read_bytes() == b"existing metadata"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["red.tif", "red.tif.meta.json"]


def test_existing_asset_requires_explicit_overwrite_before_http(tmp_path: Path) -> None:
    path = tmp_path / "red.tif"
    path.write_bytes(b"existing")
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(FileExistsError):
        connector.download_asset(_item(), "red", path)
    assert not requests
    assert path.read_bytes() == b"existing"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/band.tif",
        "file:///tmp/band.tif",
        "https://name:password@example.com/band.tif",
    ],
)
def test_invalid_asset_urls_fail_before_http(url: str, tmp_path: Path) -> None:
    item = deepcopy(_item())
    item["assets"]["red"]["href"] = url
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError, match="HTTPS"):
        connector.download_asset(item, "red", tmp_path / "red.tif")
    assert not requests


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_asset_byte_limits_fail_before_http(limit: Any, tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError, match="positive integer"):
        connector.download_asset(_item(), "red", tmp_path / "red.tif", max_bytes=limit)
    assert not requests


def test_missing_asset_fails_before_http(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector, pytest.raises(ValueError, match="no asset"):
        connector.download_asset(_item(), "not-present", tmp_path / "missing.tif")
    assert not requests
