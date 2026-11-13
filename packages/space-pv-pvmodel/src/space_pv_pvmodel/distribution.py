"""Steady two-wire DC delivery to a constant-power terminal load."""

from math import isfinite, sqrt


def dc_cable_delivery(
    *,
    source_voltage_v: float,
    load_w: float,
    length_m: float,
    conductor_area_mm2: float,
    resistivity_ohm_m: float,
    density_kg_m3: float,
    minimum_voltage_fraction: float = 0.9,
) -> dict[str, float | bool]:
    """Return the high-voltage DC equilibrium and conductor-only mass.

    Length is one-way; two identical conductors form the return loop. Resistivity
    is supplied at operating temperature. The load is power at the receiving
    terminals, before any downstream converter losses. An ideal stiff source and
    purely resistive cable are assumed. The high-voltage quadratic root is not
    proof of dynamic converter stability. No equilibrium is represented by NaN
    voltage/current/loss, never by zero loss. The double-root maximum-transfer
    point is reported but fails the strict branch-margin criterion.

    Minimum receiving voltage is a fraction of source voltage, in (0.5, 1].
    Feasibility here excludes ampacity, insulation, discharge, thermal balance,
    regulation, connectors, dust, mechanical qualification and source capacity.
    """
    for name, value in locals().copy().items():
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not 0.5 < minimum_voltage_fraction <= 1:
        raise ValueError("minimum_voltage_fraction must be in (0.5, 1]")
    area = conductor_area_mm2 * 1e-6
    resistance = 2 * resistivity_ohm_m * length_m / area
    mass = 2 * length_m * area * density_kg_m3
    maximum = source_voltage_v**2 / (4 * resistance)
    ratio = load_w / maximum
    if not all(isfinite(x) and x > 0 for x in (resistance, mass, maximum, ratio)):
        raise ValueError("derived cable quantities must be finite and positive")
    equilibrium = ratio <= 1
    receiving = source_voltage_v * (1 + sqrt(1 - ratio)) / 2 if equilibrium else float("nan")
    current = load_w / receiving
    loss = current**2 * resistance
    return {
        "loop_resistance_ohm": resistance,
        "conductor_mass_kg": mass,
        "maximum_transfer_w": maximum,
        "equilibrium_exists": equilibrium,
        "receiving_voltage_v": receiving,
        "current_a": current,
        "cable_loss_w": loss,
        "source_power_w": load_w + loss,
        "cable_efficiency": load_w / (load_w + loss),
        "voltage_criterion_pass": bool(
            ratio < 1 and receiving >= source_voltage_v * minimum_voltage_fraction
        ),
    }
