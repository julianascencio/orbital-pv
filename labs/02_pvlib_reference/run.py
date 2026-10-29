"""Small pvlib-backed AM0 reference calculation using OrbitalPV."""

from __future__ import annotations

import orbitalpv as opv


def main() -> None:
    g_am0 = opv.am0_irradiance(opv.ASTRONOMICAL_UNIT_M)
    g_eff = opv.effective_irradiance_w_m2(g_am0, 1.0, 0.85, optical_factor=0.96)
    reference = opv.PvwattsReference(pdc0_w=30.0, gamma_pdc_per_c=-0.002)
    power = opv.pvwatts_dc_space(g_eff, 45.0, reference)
    print(
        f"AM0={g_am0:.2f} W/m2 effective={float(g_eff):.2f} W/m2 expected_dc={float(power):.2f} W"
    )


if __name__ == "__main__":
    main()
