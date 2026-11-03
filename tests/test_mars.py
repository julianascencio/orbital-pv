from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
import pytest

from orbitalpv import PvwattsReference, mars

DATA = Path(__file__).resolve().parents[1] / "examples/mars/_data"


def power(times, **kwargs):
    inputs: dict[str, Any] = dict(
        latitude_deg=0.0,
        declination_deg=0.0,
        sun_distance_au=1.5,
        optical_depth=0.0,
        reference=PvwattsReference(1000, -0.003),
        cell_temperature_c=25.0,
    )
    inputs.update(kwargs)
    return mars.mars_surface_power(times, **inputs)


@pytest.mark.parametrize(
    "jd,ls,dec,distance",
    [
        (2451549.50074, 277.18758, -25.22825, 1.39358),
        (2453008.07471, 327.32416, -13.42065, 1.47767),
    ],
)
def test_geometry_against_nasa_mars24_worked_examples(jd, ls, dec, distance):
    result = mars.mars_solar_parameters(jd)
    assert result["solar_longitude_deg"] == pytest.approx(ls, abs=2e-5)
    # The published Spirit declination table differs from equation D1 by 0.00025 deg.
    assert result["declination_deg"] == pytest.approx(dec, abs=3e-4)
    assert result["sun_distance_au"] == pytest.approx(distance, abs=1e-5)


def test_vacuum_equinox_energy_has_correct_sol_duration():
    times = np.linspace(0, 24, 10001)
    result = power(times)
    wh = np.trapezoid(result.dc_power_w, times / 24 * mars.MARS_SOL_SECONDS) / 3600
    expected = 1000 / 1.5**2 * mars.MARS_SOL_SECONDS / 3600 / np.pi
    assert wh == pytest.approx(expected, rel=1e-6)
    assert power([0, 6, 18, 24]).dc_power_w.eq(0).all()


def test_distance_dust_temperature_and_atmosphere_are_distinct_factors():
    clean = power([12]).dc_power_w.iloc[0]
    assert power([12], sun_distance_au=3).dc_power_w.iloc[0] == pytest.approx(clean / 4)
    assert power([12], array_dust_factor=0.4).dc_power_w.iloc[0] == pytest.approx(0.4 * clean)
    assert power([12], cell_temperature_c=-25).dc_power_w.iloc[0] == pytest.approx(1.15 * clean)
    assert power([12], optical_depth=2).dc_power_w.iloc[0] == pytest.approx(clean / 1.6)
    assert mars.dust_retention(200, loss_per_sol=0.0028) == pytest.approx(0.570766, rel=1e-5)


def test_polar_night_day_and_components_projection():
    assert power([0, 6, 12, 18], latitude_deg=90, declination_deg=-25).dc_power_w.eq(0).all()
    polar = power([0, 6, 12, 18], latitude_deg=90, declination_deg=25)
    np.testing.assert_allclose(polar.dc_power_w, polar.dc_power_w.iloc[0])
    horizontal = power([12], atmosphere="components", diffuse_horizontal_w_m2=20, optical_depth=1)
    assert horizontal.dni_w_m2.iloc[0] == pytest.approx(1361 / 1.5**2 * np.exp(-1))
    assert horizontal.poa_w_m2.iloc[0] == pytest.approx(horizontal.ghi_w_m2.iloc[0])
    south = power(
        [12],
        atmosphere="components",
        latitude_deg=45,
        tilt_deg=45,
        diffuse_horizontal_w_m2=0,
        azimuth_deg=180,
    )
    north = power(
        [12],
        atmosphere="components",
        latitude_deg=45,
        tilt_deg=45,
        diffuse_horizontal_w_m2=0,
        azimuth_deg=0,
    )
    assert south.poa_w_m2.iloc[0] == pytest.approx(1361 / 1.5**2)
    assert north.poa_w_m2.iloc[0] < 1e-10


@pytest.mark.parametrize(
    "kwargs",
    [
        {"optical_depth": -1},
        {"optical_depth": 6},
        {"optical_depth": np.nan},
        {"array_dust_factor": 1.1},
        {"latitude_deg": 91},
        {"sun_distance_au": 0},
        {"cell_temperature_c": -274},
        {"cell_temperature_c": 1000},
        {"reference": PvwattsReference(-1, 0)},
        {"tilt_deg": 10},
        {"atmosphere": "components"},
        {"atmosphere": "unknown"},
        {"declination_deg": 91},
        {"spectral_factor": -1},
    ],
)
def test_invalid_inputs_are_not_silently_clipped(kwargs):
    with pytest.raises(ValueError):
        power([12], **kwargs)


def test_components_requires_zero_night_dhi_and_simulation_converges():
    with pytest.raises(ValueError, match="night"):
        power([0], atmosphere="components", diffuse_horizontal_w_m2=10)
    kw: dict[str, Any] = dict(
        julian_date_tt=2458449.5,
        latitude_deg=4.502,
        reference=PvwattsReference(1000, 0),
        optical_depth=0.7,
        cell_temperature_c=25,
    )
    a, b = mars.simulate_mars_sol(**kw), mars.simulate_mars_sol(**kw, samples=577)
    assert a.attrs["energy_wh"] == pytest.approx(b.attrs["energy_wh"], rel=2e-4)
    assert a.elapsed_seconds.iloc[-1] == mars.MARS_SOL_SECONDS
    with pytest.raises(ValueError, match="samples"):
        mars.simulate_mars_sol(**kw, samples=2)


def test_original_observations_preserve_units_gaps_and_schema():
    energy = mars.parse_insight_energy((DATA / "insight-energy.csv").read_bytes())
    assert len(energy) == 200 and energy.sol.tolist() == list(range(1, 201))
    assert energy.estimated_array_energy_wh.iloc[0] == 4785.2052
    current = mars.parse_insight_currents((DATA / "Solar_00004-00004.txt").read_bytes())
    assert len(current) == 696
    assert current.timestamp.iloc[0] == pd.Timestamp("2018-11-30T09:42:55.086Z")
    assert current.sa771_current_a.iloc[0] == 0.000780
    assert current.timestamp.diff().max() > pd.Timedelta(hours=1)
    tau = mars.parse_insight_opacity((DATA / "nsyt_tau.csv").read_bytes())
    assert len(tau) == 758 and tau.wavelength_nm.eq(600).all()
    assert tau.optical_depth_600nm.iloc[0] == 0.793
    assert tau.optical_depth_sigma.iloc[0] == 0.281
    assert "review" in tau.attrs["archive_status"]
    with pytest.raises(ValueError):
        mars.parse_insight_energy(b"sol,power_w\n1,200\n")
    with pytest.raises(ValueError):
        mars.parse_insight_energy(b"sol,Available Array Energy (Whr)\n1,1\n1,2\n")
    with pytest.raises(ValueError):
        mars.parse_insight_opacity(b"foo,1,2,3,4,5\n")


def mock_connector(cls, body, requests):
    connector = cls()
    connector._client.close()

    def reply(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=body)

    connector._client = httpx.Client(transport=httpx.MockTransport(reply))
    return connector


def test_cache_is_offline_query_bound_and_checksum_verified(tmp_path):
    requests = []
    with mock_connector(
        mars.InSightSolarConnector, (DATA / "insight-energy.csv").read_bytes(), requests
    ) as c:
        path = tmp_path / "energy.csv"
        one = c.daily_energy(cache_path=path)
        two = c.daily_energy(cache_path=path)
        pd.testing.assert_frame_equal(one, two)
        assert len(requests) == 1 and requests[0].endswith("/16253")
        path.write_bytes(path.read_bytes() + b"\n")
        with pytest.raises(ValueError, match="SHA-256"):
            c.daily_energy(cache_path=path)
    with (
        mock_connector(mars.InSightSolarConnector, b"not energy", []) as c,
        pytest.raises(ValueError, match="MD5"),
    ):
        c.daily_energy()
    with mock_connector(
        mars.InSightOpacityConnector, (DATA / "nsyt_tau.csv").read_bytes(), []
    ) as c:
        assert len(c.optical_depth()) == 758


def test_current_connector_reports_whole_corrupt_files_and_missing_sols(monkeypatch):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("Solar_00004-00004.txt", (DATA / "Solar_00004-00004.txt").read_bytes())
        z.writestr("Solar_00005-00005.txt", b"bad\xb0 measured bytes")
    content = output.getvalue()
    monkeypatch.setattr(
        mars.InSightSolarConnector,
        "ARCHIVES",
        {"test": (1, hashlib.md5(content, usedforsecurity=False).hexdigest())},
    )
    with mock_connector(mars.InSightSolarConnector, content, []) as c:
        with pytest.raises(ValueError, match="Solar_00005"):
            c.currents(archive="test")
        frame = c.currents(archive="test", invalid_files="report")
        assert frame.sol.unique().tolist() == [4]
        assert frame.attrs["rejected_files"][0]["file"] == "Solar_00005-00005.txt"
        with pytest.raises(ValueError, match="missing"):
            c.currents(archive="test", invalid_files="report", sols=[4, 6])
        assert len(c.currents(archive="test", sols=[4])) == 696


def load_analysis():
    path = DATA.parents[2] / "analysis/mars_surface_pv/run.py"
    spec = importlib.util.spec_from_file_location("mars_analysis", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_opacity_extrapolation_or_unbounded_gap_filling():
    analysis = load_analysis()
    observations = pd.DataFrame({"sol_ltst": [0, 2, 20], "optical_depth_600nm": [0.5, 1.0, 2.0]})
    tau, gap = analysis.align_opacity(
        np.array([-1, 0, 1, 2, 10, 20, 21]), observations, max_gap_sols=3
    )
    np.testing.assert_allclose(tau, [np.nan, 0.5, 0.75, 1, np.nan, 2, np.nan], equal_nan=True)
    assert gap[4] == 18


def test_offline_hindcast_and_pinned_provenance():
    analysis = load_analysis()
    frame, report = analysis.compare()
    assert (frame.split == "calibration").sum() == 35
    assert (frame.split == "holdout").sum() == 161
    assert (frame.split == "no_opacity_support").sum() == 4
    models = report["models"]
    assert 250 < models["geometry_atmosphere_panel_dust"]["holdout"]["rmse_wh"] < 330
    assert (
        models["geometry_atmosphere_panel_dust"]["holdout"]["rmse_wh"]
        < models["geometry_only"]["holdout"]["rmse_wh"]
    )
    manifest = json.loads((DATA / "provenance.json").read_text())
    assert len(manifest["files"]) == 5
