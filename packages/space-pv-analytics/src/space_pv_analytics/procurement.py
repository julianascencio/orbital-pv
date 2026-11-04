"""Continuous-area procurement screening at a specified end-of-life power point.

This is a deterministic decision model, not a radiation, thermal, orbit-energy,
reliability or qualified flight-hardware model. All costs use one common currency.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _number(value: float, name: str, *, zero: bool = False) -> None:
    if not isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")


@dataclass(frozen=True)
class ArrayOffer:
    """Array-level inputs at a common spectrum, temperature and incidence.

    ``bol_w_m2`` includes packing and thermal effects at the chosen design point.
    Retention includes all assumed aging effects at the specified mission EOL.
    Areal mass includes deployed structure allocated per area. Procurement cost
    excludes launch. No AM1.5-to-AM0 conversion or lifetime extrapolation occurs.
    """

    name: str
    bol_w_m2: float
    eol_retention: float
    kg_m2: float
    cost_m2: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be nonempty")
        for field in ("bol_w_m2", "eol_retention", "kg_m2"):
            _number(getattr(self, field), field)
        _number(self.cost_m2, "cost_m2", zero=True)
        if self.eol_retention > 1:
            raise ValueError("eol_retention must not exceed 1")

    @property
    def eol_w_m2(self) -> float:
        return self.bol_w_m2 * self.eol_retention


@dataclass(frozen=True)
class ArraySizing:
    """Modeled sunlit power, size and procurement-plus-launch cost."""

    area_m2: float
    mass_kg: float
    eol_bus_w: float
    procurement_cost: float
    launch_cost: float
    total_cost: float
    cost_per_eol_bus_w: float


def size_array(
    offer: ArrayOffer,
    required_bus_w: float,
    *,
    margin: float = 0.2,
    bus_efficiency: float = 0.9,
    launch_cost_kg: float = 0.0,
) -> ArraySizing:
    """Size continuous area for EOL sunlit bus demand plus fractional margin.

    Launch cost is an assumed *marginal* mass price, not a launch quote. Storage,
    eclipses, fixed qualification costs, discrete panels and deployment risks
    are outside this model. ``margin=0.2`` means 20% extra power.
    """
    _number(required_bus_w, "required_bus_w")
    _number(margin, "margin", zero=True)
    _number(bus_efficiency, "bus_efficiency")
    _number(launch_cost_kg, "launch_cost_kg", zero=True)
    if bus_efficiency > 1:
        raise ValueError("bus_efficiency must not exceed 1")
    power = required_bus_w * (1 + margin)
    area = power / (offer.eol_w_m2 * bus_efficiency)
    mass = area * offer.kg_m2
    procurement = area * offer.cost_m2
    launch = mass * launch_cost_kg
    total = procurement + launch
    return ArraySizing(area, mass, power, procurement, launch, total, total / power)


def break_even_cost_m2(
    baseline: ArrayOffer, candidate: ArrayOffer, *, launch_cost_kg: float = 0.0
) -> float:
    """Maximum candidate procurement price per m² at equal EOL bus power.

    Both options must use the same margin and bus efficiency. A negative result
    means the candidate cannot break even at any nonnegative procurement price.
    The candidate's current quoted price does not enter this threshold.
    """
    _number(launch_cost_kg, "launch_cost_kg", zero=True)
    ratio = candidate.eol_w_m2 / baseline.eol_w_m2
    return ratio * (baseline.cost_m2 + baseline.kg_m2 * launch_cost_kg) - (
        candidate.kg_m2 * launch_cost_kg
    )
