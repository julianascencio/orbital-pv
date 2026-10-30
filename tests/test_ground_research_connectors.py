"""Offline HTTP/SDK contract tests: pagination, auth, provenance and original bytes."""

from __future__ import annotations

import io
import json
from hashlib import sha256
from typing import Any, cast

import httpx
import pytest

from orbitalpv.ground_research import (
    CopernicusDataSpaceConnector,
    EumetsatConnector,
    GoesABIConnector,
    PNOAConnector,
    PVInventoryConnector,
    load_pv_inventory,
)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _item(identifier):
    return {
        "type": "Feature",
        "id": identifier,
        "collection": "sentinel-2-l2a",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"datetime": "2026-01-01T00:00:00Z"},
        "assets": {"B04": {"href": "s3://private/product.jp2"}},
    }


def test_cdse_catalog_pagination_dedup_and_current_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "stac.dataspace.copernicus.eu"
        assert "authorization" not in request.headers
        if len(requests) == 1:
            assert request.method == "POST"
            assert json.loads(request.content)["bbox"] == [-1, -1, 1, 1]
            page = {
                "type": "FeatureCollection",
                "features": [_item("a")],
                "links": [{"rel": "next", "href": "/v1/search?page=2"}],
            }
        else:
            assert request.method == "GET"
            page = {"type": "FeatureCollection", "features": [_item("a"), _item("b")], "links": []}
        return httpx.Response(200, json=page)

    result = CopernicusDataSpaceConnector(client=_client(handler)).search(
        bbox=(-1, -1, 1, 1), time_min="2026-01-01", time_max="2026-01-03"
    )
    assert [item["id"] for item in result["features"]] == ["a", "b"]
    assert result["features"][0]["assets"]["B04"]["href"].startswith("s3:")
    assert result["metadata"]["license"]


def test_cdse_refuses_cross_host_pagination():
    client = _client(
        lambda _: httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
                "links": [{"rel": "next", "href": "https://untrusted.example/next"}],
            },
        )
    )
    with pytest.raises(ValueError, match="changed host"):
        CopernicusDataSpaceConnector(client=client).search(
            bbox=(-1, -1, 1, 1), time_min="2026-01-01", time_max="2026-01-03"
        )


def test_cdse_download_requires_token_and_never_persists_it(tmp_path):
    data, secret = b"original product ZIP bytes", "explicit-test-token"
    identifier = "12345678-1234-1234-1234-123456789abc"

    def handler(request):
        assert request.headers["Authorization"] == f"Bearer {secret}"
        assert str(request.url).endswith(f"Products({identifier})/$value")
        return httpx.Response(200, content=data)

    connector = CopernicusDataSpaceConnector(client=_client(handler))
    with pytest.raises(ValueError, match="token"):
        connector.download_product(identifier, tmp_path / "missing.zip", access_token="")
    target = tmp_path / "product.zip"
    receipt = connector.download_product(identifier, target, access_token=secret)
    assert target.read_bytes() == data
    assert receipt.sha256 == sha256(data).hexdigest()
    assert secret not in target.with_suffix(".zip.meta.json").read_text()
    with pytest.raises(FileExistsError):
        connector.download_product(identifier, target, access_token=secret)


def test_pnoa_original_and_wms_have_distinct_semantics_and_correct_axes(tmp_path):
    requests = []
    png = b"\x89PNG\r\n\x1a\nfixture"

    def handler(request):
        requests.append(request)
        if request.url.params.get("REQUEST") == "GetCapabilities":
            return httpx.Response(
                200,
                content=b'<WMS_Capabilities xmlns="urn:wms"><Capability><Layer><Layer><Name>OI.OrthoimageCoverage</Name><Title>PNOA</Title></Layer></Layer></Capability></WMS_Capabilities>',
            )
        if request.url.params.get("REQUEST") == "GetMap":
            assert request.url.params["VERSION"] == "1.1.1"
            assert request.url.params["BBOX"] == "-17.0,28.0,-16.0,29.0"
            assert request.url.params["SRS"] == "EPSG:4326"
            return httpx.Response(200, content=png)
        return httpx.Response(200, content=b"unchanged native COG")

    connector = PNOAConnector(client=_client(handler))
    assert connector.layers() == [{"name": "OI.OrthoimageCoverage", "title": "PNOA"}]
    native = tmp_path / "original.tif"
    connector.download_original(
        "https://image.ign.es/pnoa/native.tif",
        native,
        acquisition_date="2025-06",
        attribution="PNOA/IGN 2025",
    )
    assert native.read_bytes() == b"unchanged native COG"
    assert (
        json.loads(native.with_suffix(".tif.meta.json").read_text())["product_kind"]
        == "original_imagery"
    )
    rendered = tmp_path / "view.png"
    connector.download_map(rendered, bbox=(-17, 28, -16, 29), layer="OI.OrthoimageCoverage")
    metadata = json.loads(rendered.with_suffix(".png.meta.json").read_text())
    assert metadata["not_calibrated_reflectance"]
    assert metadata["native_resolution_m"] is None
    assert metadata["product_kind"] == "rendered_display"
    with pytest.raises(ValueError, match="IGN or CNIG"):
        connector.download_original(
            "https://untrusted.example/file.tif", native, acquisition_date="2025", attribution="x"
        )


def test_bounded_checksum_download_preserves_existing_files_and_cleans_partial(tmp_path):
    client = _client(lambda _: httpx.Response(200, content=b"0123456789"))
    connector = PVInventoryConnector(client=client)
    destination = tmp_path / "inventory.gpkg"
    with pytest.raises(ValueError, match="max_bytes"):
        connector.download("grw", destination, max_bytes=5)
    assert not destination.exists()
    with pytest.raises(ValueError, match="SHA-256"):
        connector.download("grw", destination, expected_sha256="0" * 64)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
    connector.download("grw", destination, expected_sha256=sha256(b"0123456789").hexdigest())
    provenance = json.loads(destination.with_suffix(".gpkg.meta.json").read_text())
    assert provenance["inventory"]["version"] == "v1.0-2024q2"
    assert "Planet" in provenance["inventory"]["license"]
    with pytest.raises(ValueError, match="2019-2025"):
        PVInventoryConnector.asset("andpi", year=2026)


def test_inventory_subset_preserves_source_fields_and_verifies_integrity(tmp_path):
    pytest.importorskip("shapely")

    def feature(lon):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, 0]},
            "properties": {"Source": "upstream", "AC_MW": None, "DC_MW": 1, "license": "CC-BY"},
        }

    content = json.dumps(
        {"type": "FeatureCollection", "features": [feature(0), feature(10)]}
    ).encode()
    target = tmp_path / "inventory.geojson"
    target.write_bytes(content)
    sidecar = target.with_suffix(".geojson.meta.json")
    sidecar.write_text(
        json.dumps({"sha256": sha256(content).hexdigest(), "license": "test fixture"})
    )
    subset = load_pv_inventory(target, bbox=(-1, -1, 1, 1))
    assert len(subset["features"]) == 1
    assert subset["features"][0]["properties"]["AC_MW"] is None
    assert subset["features"][0]["properties"]["DC_MW"] == 1
    assert subset["metadata"]["source"]["license"] == "test fixture"
    target.write_bytes(content + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_pv_inventory(target)


def test_goes_xml_pagination_temporal_filter_and_original_netcdf(tmp_path):
    keys = [
        f"ABI-L2-DSRF/2026/001/12/OR_ABI-L2-DSRF-M6_G19_s202600112{minute}000_e202600112{minute}100_c202600112{minute}200.nc"
        for minute in ("00", "10", "20")
    ]
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "noaa-goes19.s3.amazonaws.com"
        if request.url.path.endswith(".nc"):
            return httpx.Response(200, content=b"original netCDF bytes")
        second = request.url.params.get("continuation-token") is not None
        selected = keys[1:] if second else keys[:1]
        contents = "".join(
            f"<Contents><Key>{key}</Key><Size>100</Size><ETag>multipart-etag-2</ETag></Contents>"
            for key in selected
        )
        token = "" if second else "<NextContinuationToken>next-page</NextContinuationToken>"
        return httpx.Response(
            200,
            content=f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>{str(not second).lower()}</IsTruncated>{contents}{token}</ListBucketResult>'.encode(),
        )

    connector = GoesABIConnector(client=_client(handler))
    found = connector.search(
        satellite=19,
        product="ABI-L2-DSRF",
        time_min="2026-01-01T12:05Z",
        time_max="2026-01-01T12:20Z",
    )
    assert len(found["items"]) == 1
    item = found["items"][0]
    assert item["key"] == keys[1]
    assert item["etag_is_sha256"] is False
    target = tmp_path / "native.nc"
    connector.download(item, target)
    assert target.read_bytes() == b"original netCDF bytes"
    assert json.loads(target.with_suffix(".nc.meta.json").read_text())["license"]
    with pytest.raises(ValueError, match="satellite"):
        connector.search(
            satellite=cast(Any, 19.0),
            product="ABI-L2-DSRF",
            time_min="2026-01-01",
            time_max="2026-01-02",
        )


def test_eumdac_explicit_credentials_sdk_contract_and_license(tmp_path):
    class Product:
        def __str__(self):
            return "synthetic-sdk-product"

        def open(self):
            return io.BytesIO(b"original EUMETSAT product bytes")

    class Collection:
        def search(self, **kwargs):
            assert kwargs["bbox"] == "-17.0,28.0,-16.0,29.0"
            assert kwargs["dtstart"].tzinfo is not None
            return iter([Product(), Product()])

    class Store:
        def get_collection(self, name):
            assert name == "EO:EUM:DAT:MSG:HRSEVIRI"
            return Collection()

    with pytest.raises(ValueError, match="credentials"):
        EumetsatConnector()
    connector = EumetsatConnector(datastore=Store())
    products = connector.search(
        collection="EO:EUM:DAT:MSG:HRSEVIRI",
        time_min="2026-01-01",
        time_max="2026-01-02",
        bbox=(-17, 28, -16, 29),
        max_items=1,
    )
    assert len(products) == 1
    target = tmp_path / "eumetsat.nat"
    connector.download_product(
        products[0],
        target,
        collection="EO:EUM:DAT:MSG:HRSEVIRI",
        license_name="user-authorized collection terms",
    )
    assert target.read_bytes() == b"original EUMETSAT product bytes"
    metadata = json.loads(target.with_suffix(".nat.meta.json").read_text())
    assert metadata["license"] == "user-authorized collection terms"
    assert "consumer_secret" not in json.dumps(metadata)
