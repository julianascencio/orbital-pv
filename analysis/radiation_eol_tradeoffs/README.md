# Radiation and end-of-life sensitivity

```bash
python analysis/radiation_eol_tradeoffs/run.py --output outputs/radiation_eol_tradeoffs
```

The script integrates a **synthetic differential particle-fluence spectrum** against a declared NIEL curve, compares unattenuated and energy-dependent attenuated cases, and propagates an empirical remaining-power factor into a thermal/PV calculation. It creates `spectrum.csv`, `eol_tradeoffs.csv` and `summary.json`.

The reference snapshot contains actual computed results for the declared inputs. At five years the retained fractions are 0.92282 and 0.95407; associated modeled equilibrium-like temperatures are 317.26 K and 315.14 K. These values are not LEO/GEO predictions, qualified material performance, or an observation of shielding effectiveness.

Replace the synthetic fluence/NIEL, empirical response and optical sensitivity assumptions with compatible particle-species, material and reference-energy data before using this workflow for a mission. Supplied attenuation is not a transport solver: secondaries, energy redistribution and angular geometry are excluded. Optical feedback assumptions are explicit in the source. Research inspiration: [Xie and Li (2026)](https://doi.org/10.1016/j.renene.2026.125716); this reduced model is not a reproduction of the article.
