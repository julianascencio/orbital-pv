from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from space_pv_connectors.lisird import LisirdConnector


def _tsi_payload() -> dict:
    """Small fixture using the verified LISIRD jsond schema and source units."""
    return {
        "tsis_tsi_24hr": {
            "metadata": {
                "time": {"units": "milliseconds since 1970-01-01"},
                "tsi_1au": {"units": "W/m^2", "missing_value": "0"},
                "tsi_true_earth": {"units": "W/m^2", "missing_value": "0"},
                "measurement_uncertainty_1au": {"units": "W/m^2", "missing_value": "0"},
                "measurement_uncertainty_true_earth": {"units": "W/m^2", "missing_value": "0"},
                "avg_measurement_date": {"units": "Julian Date", "missing_value": "0"},
                "provisional_flag": {"long_name": "1=provisional, 0=final"},
            },
            "parameters": [
                "time",
                "tsi_1au",
                "tsi_true_earth",
                "measurement_uncertainty_1au",
                "measurement_uncertainty_true_earth",
                "avg_measurement_date",
                "provisional_flag",
            ],
            "data": [
                [1577880000000, 1361.4752, 1408.1773, 0.1777, 0.1844, 2458850.249779, 0],
                [1577966400000, 0, 0, 0, 0, 0, 1],
                [1578052800000, 1361.5061, 1408.2811, 0.1766, 0.1828, 2458852.027803, 1],
            ],
        }
    }


def _connector(payload: dict, requests: list[httpx.Request] | None = None) -> LisirdConnector:
    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return httpx.Response(200, content=json.dumps(payload))

    connector = LisirdConnector()
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(respond))
    return connector


def test_tsi_uses_metadata_time_units_and_preserves_fill_flags_uncertainties() -> None:
    requests: list[httpx.Request] = []
    with _connector(_tsi_payload(), requests) as connector:
        frame = connector.total_solar_irradiance(time_min="2020-01-01", time_max="2020-01-04")

    assert frame["timestamp"].tolist() == list(pd.date_range("2020-01-01T12Z", periods=3, freq="D"))
    assert frame.loc[0, "tsi_1au_w_m2"] == 1361.4752
    assert frame.loc[0, "tsi_earth_w_m2"] == 1408.1773
    assert frame.loc[0, "uncertainty_1au_w_m2"] == 0.1777
    assert frame.loc[0, "uncertainty_earth_w_m2"] == 0.1844
    assert frame["provisional_flag"].tolist() == [0, 1, 1]
    assert frame["valid_measurement"].tolist() == [True, False, True]
    assert np.isnan(frame.loc[1, "tsi_1au_w_m2"])
    assert pd.isna(frame.loc[1, "average_measurement_timestamp"])
    expected = pd.Timestamp("2020-01-01T17:59:40.905600Z")
    assert abs(frame.loc[0, "average_measurement_timestamp"] - expected) < pd.Timedelta(
        milliseconds=1
    )
    assert "time%3E=" in str(requests[0].url)
    assert "time%3C2020-01-04" in str(requests[0].url)
    assert frame.attrs["provenance"]["request"]["dataset_id"] == "tsis_tsi_24hr"
    assert frame.attrs["source_units"]["tsi_1au"] == "W/m^2"


def test_range_is_end_exclusive_and_applied_to_nominal_time() -> None:
    with _connector(_tsi_payload()) as connector:
        frame = connector.total_solar_irradiance(
            time_min="2020-01-01T12Z", time_max="2020-01-02T12Z"
        )
    assert len(frame) == 1
    assert frame.iloc[0]["timestamp"] == pd.Timestamp("2020-01-01T12Z")


def test_empty_valid_response_keeps_schema_and_does_not_fabricate_measurements() -> None:
    payload = _tsi_payload()
    payload["tsis_tsi_24hr"]["data"] = []
    with _connector(payload) as connector:
        frame = connector.total_solar_irradiance(time_min="2020-01-01", time_max="2020-01-02")
    assert frame.empty
    assert {"timestamp", "tsi_1au_w_m2", "tsi_earth_w_m2", "valid_measurement"} <= set(
        frame.columns
    )


def test_source_http_error_does_not_create_a_fake_cache(tmp_path: Path) -> None:
    with LisirdConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(503, text="Unavailable"))
        )
        path = tmp_path / "unavailable.json"
        with pytest.raises(httpx.HTTPStatusError):
            connector.total_solar_irradiance(
                time_min="2020-01-01", time_max="2020-01-02", cache_path=path
            )
    assert not path.exists()


def test_julian_nominal_units_are_supported_without_assuming_epoch_milliseconds() -> None:
    payload = _tsi_payload()
    body = payload["tsis_tsi_24hr"]
    body["metadata"]["time"]["units"] = "Julian Date"
    body["data"] = [[2458850.0, 1361.4752, 1408.1773, 0.1777, 0.1844, 2458850.0, 0]]
    with _connector(payload) as connector:
        frame = connector.total_solar_irradiance(time_min="2020-01-01", time_max="2020-01-02")
    assert frame.iloc[0]["timestamp"] == pd.Timestamp("2020-01-01T12Z")


def test_response_cache_is_bound_to_query_and_checksum(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    path = tmp_path / "tsi.json"
    with _connector(_tsi_payload(), requests) as connector:
        first = connector.total_solar_irradiance(
            time_min="2020-01-01", time_max="2020-01-04", cache_path=path
        )
        cached = connector.total_solar_irradiance(
            time_min="2020-01-01", time_max="2020-01-04", cache_path=path
        )
        pd.testing.assert_frame_equal(first, cached)
        assert len(requests) == 1
        assert json.loads(path.read_text()) == _tsi_payload()
        assert path.with_suffix(".json.meta.json").exists()
        with pytest.raises(ValueError, match="different query"):
            connector.total_solar_irradiance(
                time_min="2021-01-01", time_max="2021-02-01", cache_path=path
            )
        path.write_text("{}")
        with pytest.raises(ValueError, match="SHA-256"):
            connector.total_solar_irradiance(
                time_min="2020-01-01", time_max="2020-01-04", cache_path=path
            )


def test_spectral_rows_preserve_quality_bits_and_missing_spectrum_bins() -> None:
    payload = {
        "tsis_ssi_24hr": {
            "metadata": {
                "time": {"units": "milliseconds since 1970-01-01"},
                "wavelength": {"units": "nm"},
                "irradiance_1au": {"units": "W/m^2/nm", "missing_value": "NaN"},
                "irradiance_true_earth": {"units": "W/m^2/nm", "missing_value": "NaN"},
                "quality": {"units": "Bit Flag"},
            },
            "parameters": [
                "time",
                "wavelength",
                "irradiance_1au",
                "irradiance_true_earth",
                "quality",
            ],
            "data": [
                [1577880000000, 300, 0.6, 0.62, 0],
                [1577880000000, 350, 0.8, 0.83, 4],
                [1577880000000, 400, None, None, 1],
            ],
        }
    }
    with _connector(payload) as connector:
        frame = connector.spectral_irradiance(time_min="2020-01-01", time_max="2020-01-02")
    assert len(frame) == 3
    assert frame["wavelength_nm"].tolist() == [300, 350, 400]
    assert frame["quality_flag"].tolist() == [0, 4, 1]
    assert frame["quality_good"].tolist() == [True, False, False]
    assert frame["valid_measurement"].tolist() == [True, True, False]
    assert frame.loc[0, "irradiance_earth_w_m2_nm"] == 0.62


@pytest.mark.parametrize("mutation", ["units", "time_units", "row_width", "missing_field"])
def test_schema_changes_fail_clearly(mutation: str) -> None:
    payload = deepcopy(_tsi_payload())
    body = payload["tsis_tsi_24hr"]
    if mutation == "units":
        body["metadata"]["tsi_1au"]["units"] = "unknown"
    elif mutation == "time_units":
        body["metadata"]["time"]["units"] = "days from some epoch"
    elif mutation == "row_width":
        body["data"][0].pop()
    else:
        body["parameters"][1] = "renamed_irradiance"
    with _connector(payload) as connector, pytest.raises(ValueError):
        connector.total_solar_irradiance(time_min="2020-01-01", time_max="2020-01-04")


def test_invalid_bounds_and_unmeasured_dataset_are_rejected_before_http() -> None:
    requests: list[httpx.Request] = []
    with _connector({}, requests) as connector:
        with pytest.raises(ValueError, match="measured TSI"):
            connector.total_solar_irradiance(
                "historical_tsi", time_min="2020-01-01", time_max="2021-01-01"
            )
        with pytest.raises(ValueError, match="later"):
            connector.total_solar_irradiance(time_min="2020-01-01", time_max="2019-01-01")
        with pytest.raises(ValueError, match="31 days"):
            connector.spectral_irradiance(time_min="2020-01-01", time_max="2021-01-01")
    assert not requests
