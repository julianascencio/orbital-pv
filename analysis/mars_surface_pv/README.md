# Mars surface PV: InSight hindcast

```bash
uv sync --all-packages --group dev --group lab
PYTHONPATH=src uv run python analysis/mars_surface_pv/run.py
```

No network access is needed. Sources are in `examples/mars/_data` with attribution, original bytes and SHA-256 provenance. The runner verifies every input and writes `outputs/mars_surface_pv/insight_comparison.csv` and `summary.json`.

The model uses NASA Mars24 seasonal geometry, a frozen-season sol integral, the existing PVWatts adapter, the Lorenz horizontal attenuation proxy and a fixed 0.0028 fractional panel loss per sol. The representative date is derived from an actual current record's UTC/LMST header. TT–UTC=69.184 seconds applies specifically to these historical 2018–2019 dates. Cell temperature is held at its reference value; the fitted response scale absorbs unmodelled electrical/thermal effects.

Only an amplitude is fitted on supported sols 5–39. The energy comparison uses sols 40–200; it is a retrospective reconstruction with interpolated observed camera opacity, not a forecast. The 15-sol interpolation limit is an analysis policy, not a source measurement resolution. No extrapolation is performed. Source sigmas are retained in the native data but not propagated to model confidence bounds.

Expected benchmark: 35 calibration sols, 161 comparison sols, 4 unsupported early sols. Dust-aware RMSE 289.5 Wh/sol (10.2%), bias +255.0 Wh/sol; geometry-only RMSE 1327.6 Wh/sol. See `reference_summary.json` for the reproducible reference result. This is a same-mission comparison with a literature-informed dust rate, not independent validation of that rate. No outliers are removed from the eligible energy series.

Live connector validation covered all five current archives: 3,733,808 parsed rows across 1,306 valid sol files. Four source files are rejected/reported: byte corruption on sols 169/192; NA-only placeholders on sols 916/941. Daily energy and the PDS opacity endpoint were also fetched successfully. The opacity provider URL is in its review tree; status is preserved explicitly.
