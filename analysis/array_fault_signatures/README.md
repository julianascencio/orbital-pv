# Synthetic array fault signatures

```bash
python analysis/array_fault_signatures/run.py --output outputs/array_fault_signatures
```

Two parallel strings, each with three generating substrings, are compared across healthy, shaded, bypassed-open, unbypassed-open and shorted scenarios. The script writes `iv_curves.csv` and `summary.json`. Reference sampled maximum powers are approximately 495.08 W healthy, 336.08 W with the selected shaded/bypassed cases, 247.54 W with one open string, and 340.86 W with one shorted substring.

Those are calculated circuit cases, not faults detected or labeled in spacecraft telemetry. A bypassed-open generating branch differs from an open circuit with no bypass path. The model includes ideal diode behavior, series resistance, constant bypass drop and ideal string blocking; it omits leakage, reverse breakdown, hot spots and arcing. MPP values are sampled-grid maxima, so increase grid resolution when necessary.

Research inspiration: [Zhang et al. (2026)](https://doi.org/10.1016/j.ast.2026.112139). This implementation is an independently written reduced circuit model.
