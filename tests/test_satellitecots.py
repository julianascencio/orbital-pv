import json
from hashlib import sha256

import httpx
import numpy as np
import pandas as pd
import pytest

from space_pv_connectors import satellitecots
from space_pv_connectors.satellitecots import (
    SatelliteCOTSConnector,
    load_bupt1_telemetry,
    normalize_bupt1_telemetry,
)


def _raw():
    return pd.DataFrame(
        {
            "Time": ["2023-03-22 04:12:37", "2023-03-22 04:12:38", "2023-03-22 04:12:39"],
            "Total_U": [16000] * 3,
            "Total_I": [1500] * 3,
            "MPPT1_Uin": [14000] * 3,
            "MPPT1_Iin": [1000, np.nan, -2],
            "MPPT1_Iout": [700] * 3,
            "MPPT2_Uin": [15000] * 3,
            "MPPT2_Iin": [500] * 3,
            "MPPT2_Iout": [400] * 3,
            "BATTERY1_U": [16000] * 3,
            "BATTERY1_I": [-200] * 3,
            "BATTERY2_U": [16000] * 3,
            "BATTERY2_I": [-200] * 3,
            "ATLAS_A_TEMP": [0, -5, 25],
            "I_Atlas200DK-A": [2000] * 3,
        }
    )


def test_normalizer_keeps_input_output_bus_and_signed_readings_distinct():
    frame = normalize_bupt1_telemetry(_raw())
    assert frame.timestamp.dt.tz is None
    assert frame.attrs["source_timezone"] is None
    assert frame.loc[0, "pv_input_power_w"] == pytest.approx(21.5)
    assert frame.loc[0, "solar_bus_power_w"] == pytest.approx(17.6)
    assert frame.loc[0, "bus_power_w"] == pytest.approx(24)
    assert frame.loc[0, "battery_source_signed_power_w"] == pytest.approx(-6.4)
    assert frame.loc[0, "atlas_a_current_a"] == 2
    assert frame.loc[0, "atlas_a_temperature_c"] == 0
    assert np.isnan(frame.loc[1, "pv_input_power_w"])
    assert frame.loc[2, "mppt_1_input_current_a"] == -0.002
    utc = normalize_bupt1_telemetry(_raw(), source_timezone="Asia/Shanghai")
    assert utc.timestamp.iloc[0] == pd.Timestamp("2023-03-21T20:12:37Z")
    assert "Caller-supplied" in utc.attrs["timestamp_basis"]


def test_multiplexed_rows_remain_group_measurements_and_repeated_clock_visible():
    raw = pd.DataFrame(
        {
            "Time": ["2023/3/2 00:00"] * 2,
            "Total_U": [16000] * 2,
            "Total_I": [1500] * 2,
            "MPPT_Group": [0, 1],
            "MPPT_Uin": [14000, 15000],
            "MPPT_Iin": [1000, 500],
            "MPPT_Iout": [700, 400],
            "BATTERY_Group": [2, 3],
        }
    )
    frame = normalize_bupt1_telemetry(raw, source="multiplexed")
    assert frame.duplicate_timestamp.all()
    assert frame.mppt_group.tolist() == [0, 1]
    assert "solar_bus_power_w" not in frame
    np.testing.assert_allclose(frame.group_pv_input_power_w, [14, 7.5])


def test_loader_checksum_bounds_and_no_silent_timezone_assumption(tmp_path):
    path = tmp_path / "telemetry.zip"
    _raw().to_csv(
        path, index=False, compression={"method": "zip", "archive_name": "telemetry_all.csv"}
    )
    with pytest.raises(ValueError, match="pinned source checksum"):
        load_bupt1_telemetry(path)
    frame = load_bupt1_telemetry(
        path,
        verify_source=False,
        chunksize=1,
        time_min="2023-03-22 04:12:38",
        time_max="2023-03-22 04:12:39",
    )
    assert len(frame) == 1
    assert frame.source_row.iloc[0] == 1
    assert not frame.attrs["verified_source"]
    with pytest.raises(ValueError, match="timezone interpretation"):
        load_bupt1_telemetry(path, verify_source=False, time_min="2023-03-22T00:00Z")


def test_download_pinning_atomic_failure_and_cache_provenance(tmp_path, monkeypatch):
    content = b"Time,Total_U,Total_I\n2023-03-22,16000,1500\n"
    digest = sha256(content).hexdigest()
    monkeypatch.setitem(satellitecots._SOURCES, "multiplexed", ("test.csv", digest, len(content)))
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=content)

    path = tmp_path / "test.csv"
    with SatelliteCOTSConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(respond))
        receipt = connector.download(path, source="multiplexed")
        repeated = connector.download(path, source="multiplexed")
        assert receipt == repeated
        assert len(calls) == 1
        provenance = json.loads(path.with_name(path.name + ".provenance.json").read_text())
        assert provenance["source_schema"] == "multiplexed"
        assert "Not declared" in provenance["license"]
        path.write_bytes(b"damaged")
        with pytest.raises(ValueError, match="pinned source checksum"):
            connector.download(path, source="multiplexed")
        monkeypatch.setitem(
            satellitecots._SOURCES, "multiplexed", ("test.csv", "bad", len(content))
        )
        with pytest.raises(ValueError, match="pinned source checksum"):
            connector.download(path, source="multiplexed", refresh=True)
        assert path.read_bytes() == b"damaged"
        assert not path.with_name(path.name + ".download").exists()
