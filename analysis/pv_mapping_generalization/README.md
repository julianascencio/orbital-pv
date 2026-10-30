# Geographic transfer of PV mapping

Run the real, offline Sentinel-2/OSM experiment:

```bash
python -m pip install '.[ground-research,examples]'
python analysis/pv_mapping_generalization/run.py --output outputs/pv_mapping_generalization
```

The output must be empty. `--data` selects a cache with the same `pv-sites.json`
and provenance-checked native image assets. Models fit only Cestas. Tenerife
is geographically held out; its OSM generator polygons are used only as a weak
evaluation reference. The explicit assumption that unlisted background is
negative can penalize real PV missing from OSM. Reference and image dates also
differ. This is weak-label agreement, not surveyed detection accuracy.

The comparison includes balanced standardized logistic regression, the existing
spectral random forest, a fixed zero NDPI threshold, and the authors' adaptive
ANDPI histogram rule applied to the whole scene. The last is a standalone
adaptation: it omits the paper's prior-inventory fusion. Its failure here should
not be interpreted as a measured failure of the complete published pipeline.
No target labels choose a threshold, feature, hyperparameter or training split.

The reproducible October 2026 cache gave F1/IoU of 0.2222/0.1250 for logistic,
0.4541/0.2937 for RF, 0.0581/0.0299 for NDPI >= 0, and 0/0 for standalone
ANDPI. RF scores here have no connected-component area filtering, which differs
from the older gallery's filtered 0.452 result. Negative results remain in the
report. Reference metrics are in `reference_results.json`.

Outputs: `report.json` with model/label provenance and source checksums,
`heldout_metrics.csv`, score/mask/validity NPZ files and `geographic_transfer.png`.
The report includes precision, recall, F1, IoU, known-support area bias,
false-positive rate and completely labelled false-positive object counts.

Source imagery retains Copernicus Sentinel terms; OSM labels require attribution
to OpenStreetMap contributors under ODbL. The [ANDPI paper](https://doi.org/10.1016/j.jag.2025.105005)
was published in December 2025; its code is pinned and the MIT notice is retained.
