"""Empirical AM0 space-solar-cell technology simulator.

The built-in technology templates are educational/reference parameterizations
anchored to published NASA space-PV performance ranges and representative
datasheet-style AM0 points. They are not qualification models for a specific
manufacturer part.

For multijunction devices, OrbitalPV uses an empirical I-V shape rather than a
terrestrial single-diode model because junction-specific spectral response,
current matching, tunnel junctions, radiation damage and temperature behavior
must ultimately be modelled separately for mission-grade work.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AM0_REFERENCE_IRRADIANCE_W_M2 = 1361.0
REFERENCE_TEMPERATURE_C = 28.0
REFERENCE_RADIATION_FLUENCE_E_CM2 = 1.0e15


@dataclass(frozen=True)
class SpaceCellTechnology:
    """Reference parameterization for a space photovoltaic cell technology."""

    slug: str
    name: str
    family: str
    junctions: int
    efficiency_am0: float
    voc_v: float
    vmp_v: float
    jsc_ma_cm2: float
    jmp_ma_cm2: float
    temp_coeff_current_per_c: float
    temp_coeff_voltage_per_c: float
    radiation_retention_at_1e15: float
    reference_temperature_c: float = REFERENCE_TEMPERATURE_C
    reference_irradiance_w_m2: float = AM0_REFERENCE_IRRADIANCE_W_M2
    notes: str = ""


@dataclass(frozen=True)
class SpaceCellSimulation:
    """Simulated I-V/P-V result for one cell technology and operating point."""

    technology: SpaceCellTechnology
    irradiance_w_m2: float
    cell_temperature_c: float
    fluence_1mev_e_cm2: float
    radiation_factor: float
    voltage_v: np.ndarray
    current_density_ma_cm2: np.ndarray
    power_density_w_m2: np.ndarray
    voc_v: float
    isc_ma_cm2: float
    vmp_v: float
    imp_ma_cm2: float
    pmp_w_m2: float
    efficiency: float


SPACE_CELL_TECHNOLOGIES: dict[str, SpaceCellTechnology] = {
    "silicon": SpaceCellTechnology(
        slug="silicon",
        name="Crystalline silicon",
        family="Si",
        junctions=1,
        efficiency_am0=0.168,
        voc_v=0.628,
        vmp_v=0.528,
        jsc_ma_cm2=45.8,
        jmp_ma_cm2=43.4,
        temp_coeff_current_per_c=0.0005,
        temp_coeff_voltage_per_c=-0.0049,
        radiation_retention_at_1e15=0.72,
        notes="Heritage/high-efficiency silicon AM0 baseline.",
    ),
    "gaas": SpaceCellTechnology(
        slug="gaas",
        name="Single-junction GaAs",
        family="GaAs",
        junctions=1,
        efficiency_am0=0.19,
        voc_v=0.98,
        vmp_v=0.90,
        jsc_ma_cm2=30.0,
        jmp_ma_cm2=28.73,
        temp_coeff_current_per_c=0.0004,
        temp_coeff_voltage_per_c=-0.0025,
        radiation_retention_at_1e15=0.75,
        notes="Representative heritage single-junction GaAs AM0 baseline.",
    ),
    "triple_junction": SpaceCellTechnology(
        slug="triple_junction",
        name="InGaP/GaAs/Ge triple-junction",
        family="III-V 3J",
        junctions=3,
        efficiency_am0=0.295,
        voc_v=2.70,
        vmp_v=2.411,
        jsc_ma_cm2=17.2,
        jmp_ma_cm2=16.71,
        temp_coeff_current_per_c=0.0004,
        temp_coeff_voltage_per_c=-0.0023,
        radiation_retention_at_1e15=0.84,
        notes="Representative lattice-matched 3J space-cell baseline.",
    ),
    "four_junction": SpaceCellTechnology(
        slug="four_junction",
        name="Four-junction III-V",
        family="III-V 4J",
        junctions=4,
        efficiency_am0=0.315,
        voc_v=3.426,
        vmp_v=2.999,
        jsc_ma_cm2=15.2,
        jmp_ma_cm2=14.37,
        temp_coeff_current_per_c=0.00035,
        temp_coeff_voltage_per_c=-0.00215,
        radiation_retention_at_1e15=0.86,
        notes="Representative modern 4J III-V AM0 baseline.",
    ),
    "imm": SpaceCellTechnology(
        slug="imm",
        name="Inverted metamorphic multijunction (IMM)",
        family="III-V IMM",
        junctions=4,
        efficiency_am0=0.32,
        voc_v=4.78,
        vmp_v=4.28,
        jsc_ma_cm2=10.7,
        jmp_ma_cm2=10.12,
        temp_coeff_current_per_c=0.0003,
        temp_coeff_voltage_per_c=-0.0020,
        radiation_retention_at_1e15=0.88,
        notes="Representative high-efficiency IMM AM0 baseline.",
    ),
}

_ALIASES = {
    "si": "silicon",
    "c_si": "silicon",
    "crystalline_silicon": "silicon",
    "gaas_single_junction": "gaas",
    "single_junction_gaas": "gaas",
    "3j": "triple_junction",
    "tj": "triple_junction",
    "ingap_gaas_ge": "triple_junction",
    "4j": "four_junction",
    "iii_v_4j": "four_junction",
    "inverted_metamorphic": "imm",
}


def list_space_cell_technologies() -> tuple[SpaceCellTechnology, ...]:
    """Return the built-in space-cell technology templates."""

    return tuple(SPACE_CELL_TECHNOLOGIES.values())


def get_space_cell_technology(name: str) -> SpaceCellTechnology:
    """Resolve a built-in technology by slug or common alias."""

    key = name.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    key = _ALIASES.get(key, key)
    try:
        return SPACE_CELL_TECHNOLOGIES[key]
    except KeyError as exc:
        available = ", ".join(SPACE_CELL_TECHNOLOGIES)
        raise ValueError(f"Unknown space-cell technology {name!r}. Available: {available}") from exc


def _iv_shape_exponent(technology: SpaceCellTechnology) -> float:
    current_fraction = technology.jmp_ma_cm2 / technology.jsc_ma_cm2
    voltage_fraction = technology.vmp_v / technology.voc_v
    return float(np.log(1.0 - current_fraction) / np.log(voltage_fraction))


def radiation_retention_factor(
    technology: str | SpaceCellTechnology,
    fluence_1mev_e_cm2: float,
) -> float:
    """Return empirical remaining power versus 1-MeV-electron equivalent fluence.

    Built-in retention values are broad comparative assumptions, not
    manufacturer qualification curves. Pass a custom SpaceCellTechnology when
    mission-specific radiation-test data are available.
    """

    tech = get_space_cell_technology(technology) if isinstance(technology, str) else technology
    if fluence_1mev_e_cm2 < 0.0:
        raise ValueError("fluence_1mev_e_cm2 must be non-negative")
    if not 0.0 < tech.radiation_retention_at_1e15 <= 1.0:
        raise ValueError("radiation_retention_at_1e15 must satisfy 0 < value <= 1")
    normalized_fluence = fluence_1mev_e_cm2 / REFERENCE_RADIATION_FLUENCE_E_CM2
    return float(tech.radiation_retention_at_1e15**normalized_fluence)


def simulate_space_cell(
    technology: str | SpaceCellTechnology,
    *,
    irradiance_w_m2: float = AM0_REFERENCE_IRRADIANCE_W_M2,
    cell_temperature_c: float = REFERENCE_TEMPERATURE_C,
    fluence_1mev_e_cm2: float = 0.0,
    points: int = 400,
) -> SpaceCellSimulation:
    """Simulate an empirical AM0 I-V and P-V curve for a space cell.

    Current scales approximately linearly with irradiance and an exposed
    radiation-retention factor. Voltage includes a logarithmic irradiance term
    and technology-specific temperature scaling. The I-V curve is shaped to
    reproduce the technology reference Voc, Vmp, Jsc and Jmp at AM0 conditions.

    This model is intended for system studies, comparisons and early mission
    design. It does not replace junction-resolved spectral/radiation models.
    """

    tech = get_space_cell_technology(technology) if isinstance(technology, str) else technology
    if irradiance_w_m2 < 0.0:
        raise ValueError("irradiance_w_m2 must be non-negative")
    if points < 2:
        raise ValueError("points must be at least 2")

    radiation_factor = radiation_retention_factor(tech, fluence_1mev_e_cm2)
    irradiance_ratio = irradiance_w_m2 / tech.reference_irradiance_w_m2

    if irradiance_ratio <= 0.0:
        voltage = np.zeros(points)
        current = np.zeros(points)
        power = np.zeros(points)
        return SpaceCellSimulation(
            technology=tech,
            irradiance_w_m2=irradiance_w_m2,
            cell_temperature_c=cell_temperature_c,
            fluence_1mev_e_cm2=fluence_1mev_e_cm2,
            radiation_factor=radiation_factor,
            voltage_v=voltage,
            current_density_ma_cm2=current,
            power_density_w_m2=power,
            voc_v=0.0,
            isc_ma_cm2=0.0,
            vmp_v=0.0,
            imp_ma_cm2=0.0,
            pmp_w_m2=0.0,
            efficiency=0.0,
        )

    delta_t_c = cell_temperature_c - tech.reference_temperature_c
    current_temp_factor = max(0.0, 1.0 + tech.temp_coeff_current_per_c * delta_t_c)
    voltage_temp_factor = max(0.0, 1.0 + tech.temp_coeff_voltage_per_c * delta_t_c)

    isc_ma_cm2 = tech.jsc_ma_cm2 * irradiance_ratio * current_temp_factor * radiation_factor
    irradiance_voltage_shift_v = 0.025 * tech.junctions * np.log(irradiance_ratio)
    voc_v = max(0.0, tech.voc_v * voltage_temp_factor + irradiance_voltage_shift_v)

    voltage_v = np.linspace(0.0, voc_v, points)
    if voc_v == 0.0 or isc_ma_cm2 == 0.0:
        current_density_ma_cm2 = np.zeros_like(voltage_v)
    else:
        shape = _iv_shape_exponent(tech)
        normalized_voltage = np.clip(voltage_v / voc_v, 0.0, 1.0)
        current_density_ma_cm2 = isc_ma_cm2 * (1.0 - normalized_voltage**shape)
        current_density_ma_cm2 = np.clip(current_density_ma_cm2, 0.0, None)

    power_density_w_m2 = voltage_v * current_density_ma_cm2 * 10.0
    mpp_index = int(np.argmax(power_density_w_m2))
    pmp_w_m2 = float(power_density_w_m2[mpp_index])
    efficiency = 0.0 if irradiance_w_m2 == 0.0 else pmp_w_m2 / irradiance_w_m2

    return SpaceCellSimulation(
        technology=tech,
        irradiance_w_m2=irradiance_w_m2,
        cell_temperature_c=cell_temperature_c,
        fluence_1mev_e_cm2=fluence_1mev_e_cm2,
        radiation_factor=radiation_factor,
        voltage_v=voltage_v,
        current_density_ma_cm2=current_density_ma_cm2,
        power_density_w_m2=power_density_w_m2,
        voc_v=voc_v,
        isc_ma_cm2=float(isc_ma_cm2),
        vmp_v=float(voltage_v[mpp_index]),
        imp_ma_cm2=float(current_density_ma_cm2[mpp_index]),
        pmp_w_m2=pmp_w_m2,
        efficiency=float(efficiency),
    )


__all__ = [
    "AM0_REFERENCE_IRRADIANCE_W_M2",
    "REFERENCE_RADIATION_FLUENCE_E_CM2",
    "REFERENCE_TEMPERATURE_C",
    "SPACE_CELL_TECHNOLOGIES",
    "SpaceCellSimulation",
    "SpaceCellTechnology",
    "get_space_cell_technology",
    "list_space_cell_technologies",
    "radiation_retention_factor",
    "simulate_space_cell",
]
