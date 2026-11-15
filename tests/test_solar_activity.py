import json

import httpx
import pandas as pd
import pytest

from space_pv_connectors.swpc import NoaaSwpcConnector, normalize_solar_activity


def test_kp_table_bounds_and_raw_values():
    frame = normalize_solar_activity(
        [
            ["time_tag", "Kp"],
            ["2026-01-01 00:00:00", "5.67"],
            ["2026-01-01 03:00:00", "-1"],
            ["2026-01-01 06:00:00", "10"],
        ],
        "kp",
    )
    assert frame.valid_measurement.tolist() == [True, False, False]
    assert frame.kp.iloc[0] == 5.67
    assert frame.Kp.iloc[1] == "-1"
    assert str(frame.timestamp.dt.tz) == "UTC"


def test_xray_channels_and_invalid_flux_are_preserved():
    records = [
        dict(time_tag="2026-01-01T00:00:00Z", satellite=18, energy=band, flux=flux)
        for band, flux in [("0.1-0.8nm", 1e-5), ("0.05-0.4nm", -999), ("0.1-0.8nm", None)]
    ]
    frame = normalize_solar_activity(records, "xrays")
    assert frame.valid_measurement.tolist() == [True, False, False]
    assert frame.energy.tolist() == [r["energy"] for r in records]
    assert frame.attrs["units"] == {"flux_w_m2": "W m^-2"}


@pytest.mark.parametrize(
    "payload,product",
    [
        ({}, "xrays"),
        ([{}], "alerts"),
        ([["time_tag", "Kp"], ["bad", "2"]], "kp"),
        ([["time_tag", "Kp"], ["2026-01-01"]], "kp"),
    ],
)
def test_bad_schema_fails(payload, product):
    with pytest.raises(ValueError):
        normalize_solar_activity(payload, product)


@pytest.mark.parametrize("product", ["xrays", "kp", "alerts"])
def test_empty_is_not_quiet(product):
    assert normalize_solar_activity([], product).empty


def test_cache_provenance_refresh_and_mismatch(tmp_path):
    calls = []
    payload = [
        dict(issue_datetime="2026-01-01 12:00:00", product_id="TEST", message="Test bulletin")
    ]

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    with NoaaSwpcConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(respond))
        path = tmp_path / "alerts.json"
        first = connector.solar_activity("alerts", cache_path=path)
        second = connector.solar_activity("alerts", cache_path=path)
        pd.testing.assert_frame_equal(first, second)
        assert len(calls) == 1
        assert first.message.iloc[0] == "Test bulletin"
        assert json.loads(path.read_text()) == payload
        with pytest.raises(ValueError, match="mismatch"):
            connector.solar_activity("kp", cache_path=path)
        connector.solar_activity("alerts", cache_path=path, refresh=True)
        assert len(calls) == 2
        path.write_text("[]")
        with pytest.raises(ValueError, match="checksum"):
            connector.solar_activity("alerts", cache_path=path)


def test_http_failure_does_not_cache(tmp_path):
    with NoaaSwpcConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(503))
        )
        path = tmp_path / "failed.json"
        with pytest.raises(httpx.HTTPStatusError):
            connector.solar_activity("xrays", cache_path=path)
        assert not path.exists()


def test_current_kp_object_schema_and_xray_contamination():
    kp = normalize_solar_activity(
        [{"time_tag": "2026-01-01T00:00:00", "Kp": 5.0, "station_count": 8}], "kp"
    )
    assert kp.kp.iloc[0] == 5
    assert kp.station_count.iloc[0] == 8
    records = [
        {
            "time_tag": "2026-01-01T00:00:00Z",
            "satellite": 18,
            "energy": "0.1-0.8nm",
            "flux": 1e-6,
            "electron_contaminaton": flag,
        }
        for flag in [True, False, None]
    ]
    frame = normalize_solar_activity(records, "xrays")
    assert frame.quality_good.tolist() == [False, True, False]
    assert frame.valid_measurement.all()
