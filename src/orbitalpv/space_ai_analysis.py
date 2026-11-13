"""Reproducible tables linking paper evidence to orbital compute screening."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .orbit import circular_orbit_period_s
from .orbital_compute import OrbitalComputeSpec, screen_orbital_compute
from .physics import BatterySpec
from .space_ai import (
    FormationSpec,
    OpticalLinkSpec,
    confocal_spatial_geometry,
    formation_metrics,
    launch_energy_cost_parity,
    launch_learning_price,
    launched_power_cost,
    load_space_ai_evidence,
    optical_link_budget,
    radiation_event_screen,
)


def space_ai_trade_study(evidence: dict | None = None) -> dict[str, pd.DataFrame]:
    """Return offline sensitivity tables; no forecast or qualification verdict.

    Paper inputs, independently calculated values and analyst scenarios retain
    distinct fields. Read the evidence snapshot for page locators and caveats.
    No external service is contacted and no output files are written here.
    """
    evidence = load_space_ai_evidence() if evidence is None else evidence
    optical = OpticalLinkSpec(**evidence["optical"]["inputs"])
    formation = FormationSpec(**evidence["formation"]["inputs"])
    radiation, economics = evidence["radiation"], evidence["economics"]
    assumed = evidence["engineering_assumptions"]
    solar = evidence["solar_estimate"]
    tables = {
        "solar_estimate": pd.DataFrame(
            [
                {
                    "paper_array_estimate_kw": solar["array_area_m2"]
                    * solar["packing_fraction"]
                    * solar["efficiency_am0_assumed"]
                    * solar["irradiance_w_m2"]
                    / 1000,
                    "table_1_rounded_power_kw": economics["proxies"][0]["power_kw"],
                    "evidence_kind": solar["evidence_kind"],
                }
            ]
        ),
        "optical_links": optical_link_budget(np.geomspace(20_000, 5_000_000, 100), optical),
        "spatial_geometry": pd.DataFrame(
            [
                confocal_spatial_geometry(
                    aperture_diameter_m=optical.aperture_diameter_m,
                    wavelength_m=optical.wavelength_m,
                    beams_per_axis=n,
                )
                for n in (1, 2, 4)
            ]
        ),
        "formation": formation_metrics(
            np.linspace(0, circular_orbit_period_s(formation.altitude_m), 121), formation
        ),
    }
    tables["radiation_events"] = pd.DataFrame(
        [
            {
                "event_kind": name,
                "dose_per_event_rad_si": dose,
                **radiation_event_screen(
                    annual_dose_rad_si=radiation["annual_dose_rad_si"],
                    dose_per_event_rad_si=dose,
                    mission_years=radiation["mission_years"],
                    device_count=assumed["device_count"],
                    inferences_per_second_per_device=assumed["inferences_per_second_per_device"],
                ),
            }
            for name, dose in radiation["dose_per_event_rad_si"].items()
        ]
    )
    mission_dose = radiation["annual_dose_rad_si"] * radiation["mission_years"]
    tables["tid_context"] = pd.DataFrame(
        [
            {
                "mission_dose_rad_si": mission_dose,
                "hbm_irregularity_onset_rad_si": radiation["hbm_irregularity_onset_rad_si"],
                "maximum_tested_tid_rad_si": radiation["maximum_tested_tid_rad_si"],
                "hbm_onset_to_mission_dose_ratio": radiation["hbm_irregularity_onset_rad_si"]
                / mission_dose
                if mission_dose > 0
                else None,
                "interpretation": "observed_test_context_not_guaranteed_survival",
            }
        ]
    )
    rows = []
    for proxy in economics["proxies"]:
        for price in economics["launch_prices_usd_kg"]:
            computed = launched_power_cost(
                **{k: proxy[k] for k in ("mass_kg", "power_kw", "lifetime_years")},
                launch_price_usd_kg=price,
            )
            reported = proxy.get(f"reported_cost_{price:g}_usd_kw_year")
            rows.append(
                {
                    "proxy": proxy["name"],
                    "launch_price_usd_kg": price,
                    "calculated_usd_kw_year": computed,
                    "paper_reported_usd_kw_year": reported,
                    "difference_percent": 100 * (computed / reported - 1)
                    if reported is not None
                    else None,
                }
            )
    tables["launched_power"] = pd.DataFrame(rows)
    tables["learning_curve"] = pd.DataFrame(
        [
            {
                "cumulative_mass_t": mass,
                "learning_rate": learning,
                "price_usd_kg": launch_learning_price(
                    initial_price_usd_kg=economics["initial_price_usd_kg"],
                    initial_cumulative_mass_t=economics["initial_cumulative_mass_t"],
                    cumulative_mass_t=float(mass),
                    learning_rate=learning,
                ),
            }
            for learning in (0.18, economics["learning_rate"], 0.24)
            for mass in np.geomspace(
                economics["initial_cumulative_mass_t"],
                economics["initial_cumulative_mass_t"] + economics["paper_additional_mass_t"],
                60,
            )
        ]
    )
    baseline = dict(assumed["baseline"])
    battery = BatterySpec(**baseline.pop("battery"))
    base = OrbitalComputeSpec(**baseline, battery=battery)
    rows = []
    for scenario in assumed["scenarios"]:
        spec = replace(base, **scenario["changes"])
        screen = screen_orbital_compute(spec)
        compute_kw = float(screen["sustainable_compute_kw"])
        parity = (
            launch_energy_cost_parity(
                mass_kg=assumed["mass_kg"],
                continuous_compute_kw=compute_kw,
                lifetime_years=assumed["lifetime_years"],
                electricity_usd_kwh=assumed["electricity_usd_kwh"],
                terrestrial_pue=assumed["terrestrial_pue"],
                utilization=assumed["compute_utilization"],
            )
            if compute_kw > 0
            else 0.0
        )
        rows.append(
            {
                "scenario": scenario["name"],
                **screen,
                "launch_only_energy_cost_parity_usd_kg": parity,
                "evidence_kind": "synthetic_engineering_sensitivity",
            }
        )
    tables["compute_screen"] = pd.DataFrame(rows)
    return tables
