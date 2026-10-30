# Battery-aware orbital compute dispatch

```bash
python analysis/orbital_compute_dispatch/run.py --output outputs/orbital_compute_dispatch
```

Compare continuous computing with a sunlight-preferred earliest-deadline heuristic over eight **synthetic 90-minute orbits**. Both request 96 Wh of computing, with the same base load, solar input, battery and steady radiator constraint. Outputs include both dispatch time series, a task-completion table and the assumption/result summary.

The executed reference scenario completes all 96 Wh without missed energy. Moving work toward sunlight reduces battery discharge from 76.8 Wh to 38.4 Wh and raises minimum SOC from 0.54579 to 0.74789. Bus power-balance residuals are zero. These are results of this constructed case, not a universal scheduling benefit or a commercial orbital-data-center feasibility claim.

The scheduler is a heuristic, not an optimal mixed-integer solution. Radiation/environment heat load and chip-to-radiator transport must be established separately. The radiator bound excludes transient thermal storage and battery/converter heat. Cycle damage uses explicit full-depth life and exponent assumptions; it does not predict capacity, calendar aging or an actual failure date.

Research inspiration: [Razmi et al. (2026)](https://doi.org/10.1109/ACCESS.2026.3656399), [Yaqoob and Huang (2026)](https://doi.org/10.1016/j.asr.2026.06.093), and [Turyshev (2026), preprint](https://arxiv.org/abs/2604.27197). The code does not claim to reproduce their reported performance.
