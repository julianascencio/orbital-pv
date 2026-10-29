from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class DeSotoParameters:
    alpha_sc: float
    a_ref: float
    i_l_ref: float
    i_o_ref: float
    r_sh_ref: float
    r_s: float
    eg_ref: float = 1.121
    degdt: float = -0.0002677


def single_diode_points(
    effective_irradiance_w_m2: float | np.ndarray,
    cell_temperature_c: float | np.ndarray,
    params: DeSotoParameters,
) -> dict[str, np.ndarray]:
    """pvlib De Soto + single-diode reference path for single-junction cells.

    This is deliberately separated from multi-junction space-cell modeling. It is useful
    for silicon/single-junction experiments, model validation, and as a familiar pvlib
    baseline, but it should not be presented as a native III-V multi-junction model.
    """
    import pvlib

    il, i0, rs, rsh, nnsvth = pvlib.pvsystem.calcparams_desoto(
        np.asarray(effective_irradiance_w_m2, dtype=float),
        np.asarray(cell_temperature_c, dtype=float),
        alpha_sc=params.alpha_sc,
        a_ref=params.a_ref,
        I_L_ref=params.i_l_ref,
        I_o_ref=params.i_o_ref,
        R_sh_ref=params.r_sh_ref,
        R_s=params.r_s,
        EgRef=params.eg_ref,
        dEgdT=params.degdt,
    )
    result = pvlib.pvsystem.singlediode(il, i0, rs, rsh, nnsvth)
    return {key: np.asarray(value, dtype=float) for key, value in result.items()}
