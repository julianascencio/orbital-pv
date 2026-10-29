"""Small pvlib-backed AM0 reference calculation."""

from __future__ import annotations

from space_pv_pvmodel import PvwattsReference, effective_irradiance_w_m2, pvwatts_dc_space
from space_pv_space_env import am0_irradiance


def main() -> None:
    g_am0 = am0_irradiance(149_597_870_700.0)
    g_eff = effective_irradiance_w_m2(g_am0, 1.0, 0.85, optical_factor=0.96)
    reference = PvwattsReference(pdc0_w=30.0, gamma_pdc_per_c=-0.002)
    power = pvwatts_dc_space(g_eff, 45.0, reference)
    print(f"AM0={g_am0:.2f} W/m2 effective={float(g_eff):.2f} W/m2 expected_dc={float(power):.2f} W")


if __name__ == "__main__":
    main()
