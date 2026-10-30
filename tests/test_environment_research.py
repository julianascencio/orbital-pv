"""Physical invariants and real-format contracts for environmental inputs."""

import hashlib
import json
import sys
from types import SimpleNamespace

import httpx
import numpy as np
import pandas as pd
import pytest
import xarray as xr

import orbitalpv as opv

env = opv.environment_data


def mocked(connector, handler):
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(handler))
    return connector


def test_global_cell_area_and_uniform_earth_analytic_limit():
    radius = 6_371_008.8
    distance = radius + 550_000
    lat = np.linspace(-90, 90, 361)
    lon = np.linspace(-180, 180, 721)
    areas = env.earth_grid_cell_areas(lat, lon)
    assert areas.sum() == pytest.approx(4 * np.pi * radius**2)
    lat_grid, lon_grid = np.meshgrid(
        (lat[:-1] + lat[1:]) / 2, (lon[:-1] + lon[1:]) / 2, indexing="ij"
    )
    result = env.earth_flux_to_panel(
        [distance, 0, 0], [-1, 0, 0], lat_grid, lon_grid, np.full(areas.shape, 240.0), areas
    )
    assert result.irradiance_w_m2 == pytest.approx(240 * (radius / distance) ** 2, rel=2e-4)
    assert result.valid_view_fraction == pytest.approx(1.0)
    assert not result.partial
    away = env.earth_flux_to_panel(
        [distance, 0, 0], [1, 0, 0], lat_grid, lon_grid, np.full(areas.shape, 240.0), areas
    )
    assert away.irradiance_w_m2 == 0


def test_missing_earth_view_is_not_silently_zero_or_extrapolated():
    args = ([7e6, 0, 0], [-1, 0, 0], [0, 0], [-1, 1], [100, np.nan], [1e9, 1e9])
    incomplete = env.earth_flux_to_panel(*args)
    assert np.isnan(incomplete.irradiance_w_m2)
    assert incomplete.valid_view_fraction == pytest.approx(0.5)
    partial = env.earth_flux_to_panel(*args, allow_partial=True)
    complete = env.earth_flux_to_panel(*args[:4], [100, 100], args[5])
    assert partial.irradiance_w_m2 == pytest.approx(complete.irradiance_w_m2 / 2)
    assert partial.partial


def test_earth_view_rejects_physically_impossible_coarse_quadrature():
    area = env.earth_grid_cell_areas([-10, 10], [-10, 10])
    with pytest.raises(ValueError, match="refine"):
        env.earth_flux_to_panel([6_921_008.8, 0, 0], [-1, 0, 0], 0, 0, 240, area)


@pytest.mark.parametrize("lat,lon", [([0, 0], [0, 1]), ([-91, 0], [0, 1]), ([0, 1], [0, 361])])
def test_earth_grid_rejects_invalid_geometry(lat, lon):
    with pytest.raises(ValueError):
        env.earth_grid_cell_areas(lat, lon)


def test_noaa_filename_is_calendar_and_instrument_specific():
    url = env.PoesMetopConnector.daily_url("metop01", "2023-01-01")
    assert url.endswith("/v01r00/2023/metop01/poes_m01_20230101_proc.nc")
    with pytest.raises(ValueError):
        env.PoesMetopConnector.daily_url("noaa19", "2023-02-30")
    with pytest.raises(ValueError):
        env.PoesMetopConnector.daily_url("GOES", "2023-01-01")


def test_environment_download_integrity_cache_and_secret_redaction(tmp_path):
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        assert request.headers["Authorization"] == "Bearer private-token"
        return httpx.Response(
            200, content=b"CDF\x01example", headers={"content-type": "application/octet-stream"}
        )

    path = tmp_path / "environment.nc"
    url = "https://asdc.larc.nasa.gov/data/example.nc?temporary=secret"
    digest = hashlib.sha256(b"CDF\x01example").hexdigest()
    with mocked(env.CeresConnector(), handle) as connector:
        receipt = connector.download(
            url, path, expected_sha256=digest, bearer_token="private-token"
        )
        assert receipt.sha256 == digest
        assert "secret" not in receipt.url
        saved = path.with_suffix(".nc.receipt.json").read_text()
        assert "private-token" not in saved and "secret" not in saved
        assert connector.download(url, path, expected_sha256=digest) == receipt
        assert count == 1
        with pytest.raises(ValueError, match="verification"):
            connector.download(url.replace("temporary=secret", "subset=different"), path)
        path.write_bytes(b"corrupted")
        with pytest.raises(ValueError, match="verification"):
            connector.download(url, path)


@pytest.mark.parametrize(
    "content,headers,kwargs",
    [
        (b"12345", {}, {"max_bytes": 4}),
        (b"<html>login</html>", {"content-type": "text/html"}, {}),
        (b"data", {}, {"expected_sha256": "0" * 64}),
        (b"", {}, {}),
    ],
)
def test_failed_environment_download_does_not_leave_a_data_file(tmp_path, content, headers, kwargs):
    with (
        mocked(
            env.PoesMetopConnector(),
            lambda _: httpx.Response(200, content=content, headers=headers),
        ) as connector,
        pytest.raises(ValueError),
    ):
        connector.download("https://www.ncei.noaa.gov/data/file.nc", tmp_path / "file.nc", **kwargs)
    assert not list(tmp_path.iterdir())


def test_environment_download_restricts_provider_host(tmp_path):
    with env.CeresConnector() as connector, pytest.raises(ValueError, match="HTTPS"):
        connector.download("https://example.org/file.nc", tmp_path / "file.nc")


def test_ceres_search_pages_and_returns_data_not_documentation():
    requests = []

    def handle(request):
        requests.append(request)
        page = int(request.url.params["page_num"])
        entries = [
            {
                "id": f"G{page}",
                "links": [
                    {
                        "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                        "href": "https://asdc.larc.nasa.gov/data/one.nc",
                    },
                    {
                        "rel": "http://esipfed.org/ns/fedsearch/1.1/documentation#",
                        "href": "https://example.org/doc",
                    },
                ],
            }
        ]
        return httpx.Response(200, json={"feed": {"entry": entries}}, headers={"CMR-Hits": "2"})

    with mocked(env.CeresConnector(), handle) as connector:
        results = connector.search(
            short_name="CER_EXPLICIT_EDITION",
            version="Edition4B",
            start="2023-01-01T00:00:00Z",
            end="2023-01-02T00:00:00Z",
            page_size=1,
        )
    assert [row["id"] for row in results] == ["G1", "G2"]
    assert len(requests) == 2
    assert results[0]["data_urls"] == ["https://asdc.larc.nasa.gov/data/one.nc"]


def test_ceres_search_refuses_silent_truncation_and_naive_time():
    with mocked(
        env.CeresConnector(),
        lambda _: httpx.Response(200, json={"feed": {"entry": [{"id": "G1"}]}}),
    ) as connector:
        with pytest.raises(ValueError, match="max_pages"):
            connector.search(
                short_name="CER_A",
                version="Edition4B",
                start="2023-01-01T00:00:00Z",
                end="2023-01-02T00:00:00Z",
                page_size=1,
                max_pages=1,
            )
        with pytest.raises(ValueError, match="timezone"):
            connector.search(
                short_name="CER_A", version="Edition4B", start="2023-01-01", end="2023-01-02"
            )


def test_native_noaa_record_dimensions_and_time_metadata(tmp_path):
    dataset = xr.Dataset(
        {
            "time": (
                "time",
                [1672531200563, 1672531202563],
                {"units": "time", "long_name": "milliseconds since 1970"},
            ),
            "flux": ("flux", [1.0, -99.0], {"units": "#/cm2-s-str"}),
        },
        attrs={"Project": "POES/MetOp", "naming_authority": "gov.noaa.ngdc"},
    )
    path = tmp_path / "native_noaa.nc"
    dataset.to_netcdf(path, engine="h5netcdf")
    frame = env.read_poes_metop(path, channels=["flux"])
    assert frame.timestamp_utc.iloc[0] == pd.Timestamp("2023-01-01T00:00:00.563Z")
    assert frame.flux.tolist() == [1.0, -99.0]
    dataset.attrs.clear()
    dataset.to_netcdf(path, engine="h5netcdf", mode="w")
    with pytest.raises(ValueError, match="axis"):
        env.read_poes_metop(path, channels=["flux"])


def test_ceres_read_cf_units_missing_values_and_subset(tmp_path):
    dataset = xr.Dataset(
        data_vars={
            "sw": (("time", "lat", "lon"), [[[100.0, -999.0], [90.0, 0.0]]], {"units": "W m-2"}),
            "lw": (("time", "lat", "lon"), [[[240.0, 230.0], [250.0, 200.0]]], {"units": "W/m2"}),
        },
        coords={
            "time": pd.date_range("2023-01-01", periods=1),
            "lat": [-0.5, 0.5],
            "lon": [-0.5, 0.5],
        },
    )
    path = tmp_path / "ceres.nc"
    dataset.to_netcdf(path, engine="h5netcdf")
    frame = env.read_ceres_toa(path, shortwave_variable="sw", longwave_variable="lw")
    assert len(frame) == 4
    assert frame.toa_shortwave_w_m2.isna().sum() == 1
    assert frame.attrs["measurement_boundary"] == "top-of-atmosphere hemispheric flux"
    assert str(frame.timestamp_utc.dt.tz) == "UTC"
    subset = env.read_ceres_toa(
        path, shortwave_variable="sw", longwave_variable="lw", selectors={"lat": slice(0, 1)}
    )
    assert len(subset) == 2
    dataset["sw"].attrs["units"] = "J m-2"
    dataset.to_netcdf(path, engine="h5netcdf", mode="w")
    with pytest.raises(ValueError, match="W m-2"):
        env.read_ceres_toa(path, shortwave_variable="sw", longwave_variable="lw")


def test_poes_read_preserves_detector_units_and_quality(tmp_path):
    dataset = xr.Dataset(
        {
            "counts": (
                "time",
                [1.0, np.nan, 3.0],
                {"units": "counts/s", "long_name": "detector counts"},
            ),
            "quality": ("time", [0, 1, 0]),
        },
        coords={"time": pd.date_range("2023-01-01", periods=3, freq="2s")},
    )
    path = tmp_path / "sem.nc"
    dataset.to_netcdf(path, engine="h5netcdf")
    assert env.inspect_environment_netcdf(path)["counts"]["units"] == "counts/s"
    frame = env.read_poes_metop(path, channels=["counts"], quality_variables=["quality"])
    assert frame["counts"].isna().sum() == 1
    assert frame.attrs["units"]["counts"] == "counts/s"
    assert frame.quality.tolist() == [0, 1, 0]
    dataset = dataset.assign_coords(time=[1, 2, 3])
    dataset.to_netcdf(path, engine="h5netcdf", mode="w")
    with pytest.raises(ValueError, match="epoch"):
        env.read_poes_metop(path, channels=["counts"])


SPENVIS = """'*',7,1,2,1,2,3,2,0
'Synthetic format fixture'
'MODEL',-1,'user-selected scenario'
'ENERGY',2,1,10,'MeV'
# Reserved annotation
'TIME','s',1,'Elapsed time'
'FLUX','cm-2 s-1',2,'Integral flux','ENERGY'
0,1.0D+3,2.0D+2
1,8.0e2,1.5e2
'End of File'
"""


def test_spenvis_vectors_metadata_d_exponents_and_multiple_blocks(tmp_path):
    blocks = env.parse_spenvis(SPENVIS + SPENVIS)
    assert len(blocks) == 2
    assert blocks[0].data.columns.tolist() == ["TIME", "FLUX[0]", "FLUX[1]"]
    assert blocks[0].data.iloc[0, 1] == 1000
    assert blocks[0].metadata["ENERGY"]["values"] == (1.0, 10.0)
    assert blocks[0].variables[1].metadata_names == ("ENERGY",)
    assert blocks[0].data.attrs["units"]["FLUX[1]"] == "cm-2 s-1"
    path = tmp_path / "user_export.csv"
    path.write_text(SPENVIS)
    assert (
        env.read_spenvis(path)[0].data.attrs["source_file_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "invalid",
    [
        SPENVIS.replace("7,1,2", "8,1,2"),
        SPENVIS.replace("0,1.0D+3,2.0D+2", "0,1"),
        SPENVIS.replace("'End of File'", ""),
        SPENVIS.replace("'End of File'", "'ERROR: failed model'"),
        SPENVIS.replace("'End of File'", "'*ERROR*'"),
        SPENVIS.replace("2,3,2,0", "2,3,3,0"),
    ],
)
def test_spenvis_rejects_truncation_and_provider_errors(invalid):
    with pytest.raises(ValueError):
        env.parse_spenvis(invalid)


def test_spenvis_rejects_missing_declared_following_block():
    invalid = "'*',2,0,0,0,1,1,1,1\n'X','s',1,'Time'\n0\n'Section Break'\n"
    with pytest.raises(ValueError, match="following blocks"):
        env.parse_spenvis(invalid)


def test_spacetrack_history_cache_provenance_and_epoch_order(tmp_path):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        assert "/class/gp_history/" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {"NORAD_CAT_ID": "25544", "EPOCH": "2023-01-01T12:00:00"},
                {"NORAD_CAT_ID": "25544", "EPOCH": "2023-01-01T00:00:00"},
            ],
        )

    with mocked(env.SpaceTrackConnector(), handle) as connector:
        kwargs = {
            "start": "2023-01-01T00:00:00Z",
            "end": "2023-01-02T00:00:00Z",
            "cache_dir": tmp_path,
        }
        records = connector.gp_history(25544, **kwargs)
        assert records[0]["EPOCH"].endswith("00:00:00")
        assert connector.gp_history(25544, **kwargs) == records
        assert calls == 1
        path = next(tmp_path.glob("*.json"))
        content = json.loads(path.read_text())
        content["records"][0]["EPOCH"] = "2020-01-01"
        path.write_text(json.dumps(content))
        with pytest.raises(ValueError, match="provenance"):
            connector.gp_history(25544, **kwargs)


def test_spacetrack_history_truncation_does_not_cache(tmp_path):
    with (
        mocked(
            env.SpaceTrackConnector(), lambda _: httpx.Response(200, json=[{}, {}])
        ) as connector,
        pytest.raises(ValueError, match="max_records"),
    ):
        connector.gp_history(
            25544,
            start="2023-01-01T00:00:00Z",
            end="2023-01-02T00:00:00Z",
            cache_dir=tmp_path,
            max_records=1,
        )
    assert not list(tmp_path.iterdir())


def test_spice_transform_convention_and_unavailable_kernel_errors(monkeypatch):
    matrix = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)

    def transform(from_frame, to_frame, et):
        assert (from_frame, to_frame) == ("BODY", "J2000")
        if et < 0:
            raise RuntimeError("CK coverage missing")
        return matrix

    monkeypatch.setitem(sys.modules, "spiceypy", SimpleNamespace(pxform=transform))
    rotated = env.transform_vectors([1, 0, 0], "BODY", "J2000", [1, 2])
    np.testing.assert_allclose(rotated, [[0, 1, 0], [0, 1, 0]])
    np.testing.assert_allclose(np.linalg.norm(rotated, axis=1), 1.0)
    with pytest.raises(RuntimeError, match="coverage"):
        env.frame_rotation_matrices("BODY", "J2000", [-1])
    with pytest.raises(ValueError, match="one-dimensional"):
        env.frame_rotation_matrices("BODY", "J2000", [[1]])


def test_spice_utc_does_not_guess_time_scale(monkeypatch):
    monkeypatch.setitem(sys.modules, "spiceypy", SimpleNamespace(str2et=lambda _: 123.0))
    np.testing.assert_allclose(env.utc_to_ephemeris_seconds(["2016-12-31T23:59:60Z"]), [123])
    with pytest.raises(ValueError, match="ISO UTC"):
        env.utc_to_ephemeris_seconds(["2023-01-01T00:00:00 TDB"])
