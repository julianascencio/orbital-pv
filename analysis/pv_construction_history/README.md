# Dated footprint change and construction brackets

The default is a deliberately **synthetic** scenario; it is not construction
evidence. The bundled real image cache contains one date per site and cannot
support a real temporal claim.

```bash
python -m pip install '.[ground-research]'
python analysis/pv_construction_history/run.py --output outputs/pv_construction_history
```

For real dated inventories (GeoJSON, or vector files supported by the optional
vector dependencies):

```bash
python analysis/pv_construction_history/run.py \
  --before before.geojson --after after.geojson \
  --before-time 2024-05-01 --after-time 2025-06-01 \
  --output outputs/my_dated_inventory
```

Both inputs must describe compatible PV footprint semantics, WGS84 coverage,
and observation epochs. Use original acquisition/observation dates rather than
download, release or publication dates. Versioned GRW/ANDPI products can supply
candidate histories but inferred installation dates are not measured electrical
commissioning. Preserve their original fields, provenance and license terms.

The matching graph connects polygons by intersection/minimum area and groups
splits and merges. EPSG:6933 supplies equal-area measurements. New unmatched
objects are `newly_observed`; unmatched old objects are `not_redetected`.
Only `--complete-coverage`, an explicit assertion that both dates comprehensively
survey the same area, promotes these to added/removed-between-observations and
provides a last-absent/first-present window. Disappearance can also reflect clouds,
classification error or changed inventory scope. The algorithm does not estimate
an exact construction or commissioning date.

Outputs: unmodified input snapshots and `report.json`, containing source checksums,
group membership, footprint change, split/merge flags and optional date brackets.
