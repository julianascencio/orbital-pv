# Lab 02 — pvlib-backed reference PV model

This lab demonstrates the public **`orbitalpv` API** rather than importing the implementation packages directly.

## Install

```bash
python -m pip install orbital-pv
```

## Run

```bash
python labs/02_pvlib_reference/run.py
```

Core usage:

```python
import orbitalpv as opv

g_am0 = opv.am0_irradiance(opv.ASTRONOMICAL_UNIT_M)
g_eff = opv.effective_irradiance_w_m2(g_am0, 1.0, 0.85, optical_factor=0.96)
reference = opv.PvwattsReference(pdc0_w=30.0, gamma_pdc_per_c=-0.002)
power = opv.pvwatts_dc_space(g_eff, 45.0, reference)
```
