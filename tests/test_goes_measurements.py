import json

import httpx
import numpy as np
import pandas as pd
import pytest

from space_pv_connectors.swpc import NoaaSwpcConnector, load_goes_integral_particle_flux


def _record(flux=0.25, satellite=18, time="2026-10-23T06:45:00Z", energy=">=10 MeV"):
    return {"time_tag": time, "satellite": satellite, "flux": flux, "energy": energy}


def test_goes_units_source_identity_and_missing_flux(tmp_path):
    path = tmp_path / "flux.json"
    path.write_text(
        json.dumps([_record(), _record(-100000, satellite=19), _record(None), _record(0)])
    )
    frame = load_goes_integral_particle_flux(path, particle="protons")
    assert frame["timestamp"].iloc[0] == pd.Timestamp("2026-10-23T06:45:00Z")
    assert set(frame["satellite_id"]) == {"GOES-18", "GOES-19"}
    assert set(frame["flux_unit"]) == {"protons cm^-2 s^-1 sr^-1"}
    assert set(frame["energy_threshold_mev"]) == {10}
    assert sorted(frame["flux_cm2_s_sr"].dropna()) == [0.0, 0.25]
    assert frame["is_valid_flux"].sum() == 2
    assert frame.attrs["invalid_flux_rows"] == 2


def test_goes_cache_preserves_snapshot_and_validates_query_and_checksum(tmp_path):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, json=[_record()])

    path = tmp_path / "flux.json"
    with NoaaSwpcConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(handler))
        first = connector.goes_integral_particle_flux("protons", cache_path=path)
        cached = connector.goes_integral_particle_flux("protons", cache_path=path)
        pd.testing.assert_frame_equal(first, cached)
        assert len(requests) == 1
        with pytest.raises(ValueError, match="request or checksum mismatch"):
            connector.goes_integral_particle_flux("electrons", cache_path=path)
        path.write_text("[]")
        with pytest.raises(ValueError, match="request or checksum mismatch"):
            connector.goes_integral_particle_flux("protons", cache_path=path)
        connector.goes_integral_particle_flux("protons", cache_path=path, refresh=True)
        assert len(requests) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"particle": "ions"},
        {"particle": "protons", "role": "../x"},
        {"particle": "protons", "period": "30-day"},
    ],
)
def test_goes_rejects_unsupported_feed_parameters(kwargs):
    with NoaaSwpcConnector() as connector, pytest.raises(ValueError):
        connector.goes_integral_particle_flux(**kwargs)


@pytest.mark.parametrize(
    "record, message",
    [
        (_record(time="bad"), "invalid timestamps"),
        (_record(satellite=None), "satellite identifiers"),
        (_record(energy="10-20 keV"), "threshold in MeV"),
    ],
)
def test_goes_rejects_invalid_measurement_coordinates(tmp_path, record, message):
    path = tmp_path / "flux.json"
    path.write_text(json.dumps([record]))
    with pytest.raises(ValueError, match=message):
        load_goes_integral_particle_flux(path, particle="protons")


def test_goes_preserves_nonfinite_flux_as_invalid(tmp_path):
    path = tmp_path / "flux.json"
    path.write_text(json.dumps([_record(float("inf"))]))
    frame = load_goes_integral_particle_flux(path, particle="protons")
    assert not frame["is_valid_flux"].iloc[0]
    assert np.isnan(frame["flux_cm2_s_sr"].iloc[0])
