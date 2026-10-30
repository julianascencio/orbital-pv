# Spectral photocurrent and tandem matching

```bash
python analysis/spectral_cell_comparison/run.py --output outputs/spectral_cell_comparison
python analysis/spectral_cell_comparison/run.py --spectrum measured_spectrum.csv --output outputs/measured_spectrum
```

A supplied spectrum CSV must have `wavelength_nm` and `spectral_irradiance_w_m2_nm`. Its hash is recorded. The default instead uses a **synthetic 5772 K blackbody shape**, normalized to 1361 W/m² only over the stated 280–1800 nm interval. It is not a measured or standard AM0 reference.

Idealized external EQE windows partition the common incident spectrum between two series-connected equal-area subcells. The calculation produces `spectrum.csv`, `tandem_currents.csv` and `summary.json`. In the reference cases, a 700 nm split gives a series current of 227.13 A/m² and a 5.07% current-utilization mismatch. Those are current metrics, not efficiency or energy-yield claims.

EQE must describe each subcell in the finished stack relative to the same incident light. Adding standalone unfiltered EQEs can double count photons and is rejected. The next input for a technology comparison is measured stack EQE, voltage and temperature response. Research inspiration: [Kim et al. (2026)](https://doi.org/10.1038/s44172-026-00813-2). No supplementary software from that article is copied.
