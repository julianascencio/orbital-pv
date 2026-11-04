"""Analytic invariants and evidence-ingestion failures for array procurement."""

from dataclasses import replace
from pathlib import Path

import pytest

from space_pv_analytics.procurement import ArrayOffer, break_even_cost_m2, size_array
from space_pv_connectors.procurement import load_array_offers

BASE = ArrayOffer("baseline", 300, 0.85, 2, 1000)
CANDIDATE = ArrayOffer("candidate", 360, 0.85, 2, 1500)
INPUT = Path(__file__).resolve().parents[1] / "examples/space_business/_data/array_offers.csv"


def test_power_balance_and_equal_power_area_ratio():
    base = size_array(BASE, 10_000, launch_cost_kg=5000)
    candidate = size_array(CANDIDATE, 10_000, launch_cost_kg=5000)
    assert base.area_m2 * BASE.eol_w_m2 * 0.9 == pytest.approx(12_000)
    assert candidate.eol_bus_w == base.eol_bus_w
    assert candidate.area_m2 / base.area_m2 == pytest.approx(1 / 1.2)
    assert base.total_cost == base.procurement_cost + base.launch_cost


@pytest.mark.parametrize("launch", [0, 1000, 5000, 10_000])
@pytest.mark.parametrize("retention", [0.55, 0.85, 1])
def test_price_ceiling_equalizes_total_cost(launch, retention):
    candidate = replace(CANDIDATE, eol_retention=retention)
    ceiling = break_even_cost_m2(BASE, candidate, launch_cost_kg=launch)
    if ceiling < 0:
        assert (
            size_array(replace(candidate, cost_m2=0), 1000, launch_cost_kg=launch).total_cost
            > size_array(BASE, 1000, launch_cost_kg=launch).total_cost
        )
    else:
        for demand in (1, 10_000):
            reference = size_array(
                BASE, demand, margin=0.4, bus_efficiency=0.7, launch_cost_kg=launch
            )
            matched = size_array(
                replace(candidate, cost_m2=ceiling),
                demand,
                margin=0.4,
                bus_efficiency=0.7,
                launch_cost_kg=launch,
            )
            assert matched.total_cost == pytest.approx(reference.total_cost)


def test_no_launch_cost_and_equal_eol_density():
    assert break_even_cost_m2(BASE, CANDIDATE) == pytest.approx(1200)
    candidate = replace(CANDIDATE, eol_retention=BASE.eol_retention / 1.2)
    assert break_even_cost_m2(BASE, candidate, launch_cost_kg=5000) == pytest.approx(1000)
    assert break_even_cost_m2(BASE, CANDIDATE, launch_cost_kg=5000) == pytest.approx(3200)


@pytest.mark.parametrize(
    "field,value",
    [
        ("bol_w_m2", 0),
        ("eol_retention", 1.01),
        ("kg_m2", -1),
        ("cost_m2", -1),
        ("bol_w_m2", float("nan")),
        ("cost_m2", float("inf")),
    ],
)
def test_offer_validation(field, value):
    with pytest.raises(ValueError):
        replace(BASE, **{field: value})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bus_efficiency": 0},
        {"bus_efficiency": 1.1},
        {"margin": -0.1},
        {"launch_cost_kg": float("nan")},
    ],
)
def test_sizing_validation(kwargs):
    with pytest.raises(ValueError):
        size_array(BASE, 1000, **kwargs)


def test_loader_preserves_evidence():
    frame = load_array_offers(INPUT)
    assert frame.evidence_status.tolist() == ["modeled", "modeled"]
    assert "unverified" in frame.assumptions.iloc[1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_status", "certified"),
        ("source_url", ""),
        ("eol_retention", 1.1),
        ("bol_w_m2", float("inf")),
        ("name", "HJT scenario"),
    ],
)
def test_loader_rejects_bad_input(tmp_path, field, value):
    frame = load_array_offers(INPUT)
    frame[field] = frame[field].astype(object)
    frame.loc[1, field] = value
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_array_offers(path)
