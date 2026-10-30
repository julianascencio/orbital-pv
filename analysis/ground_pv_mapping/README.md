# Reproducible ground PV mapping analysis

This analysis trains an image classifier on Cestas, predicts footprints in
Tenerife and Chile, groups mapped features into farms, attaches historical
settlement context, and evaluates an independently calibrated capacity model.
It consumes the same verified real source snapshots as the example gallery.

Install the repository into an environment with the ground and plotting extras:

```bash
python -m pip install '.[ground,examples]'
python analysis/ground_pv_mapping/run.py --output outputs/ground_pv_mapping
```

The output directory must be empty. The script runs offline and does not
modify its inputs. Use `--data PATH` to select another directory with the same
site configuration and provenance-checked input structure. The bundled
experiment intentionally uses Cestas for training and Tenerife for evaluation;
the public model APIs accept caller-supplied training and target sites.

## Outputs

- `footprint_model.json`: trained numeric decision trees and training provenance;
  restore with `orbitalpv.PVFootprintModel.load` without executing pickle content.
- `image_validation.json`: Tenerife raw and area-filtered precision, recall, F1
  and IoU, plus scored/unknown counts and label provenance.
- `capacity_model.json`: fitted coefficients, area/AC-DC basis, calibration range
  and source. Restore with `orbitalpv.PVCapacityModel(**json.load(file))`.
- `capacity_validation.json` and `capacity_spain_holdout.csv`: country-held-out
  errors, conditional intervals, and reasons for withheld estimates.
- Per site, `farms_semantic.geojson` and `farms_dunnett2020.geojson`: grouping
  settings, source feature IDs, separate area definitions, settlement flags and
  eligible capacity estimates.
- For Tenerife and Chile, `pv_footprints.geojson`, `pv_prediction.tif`,
  `pv_prediction.json`, and `prediction.png`: image-only model output, with
  uncalibrated scores, area filtering, georeferencing and provenance.
- `summary.json`: metrics, source checksums, fixed parameters and library versions.

## Interpretation

The detector is a research baseline trained on one site. OSM generator
polygons supply weak labels, background negatives are assumed explicitly, and
the 20 m outside-boundary buffer is unknown. Tenerife is geographically held
out; its map is used only for evaluation. The image model receives no OSM data
at prediction time. Rinconada's whole-plant outline is not a panel reference,
so no panel-level accuracy is claimed there.

The capacity model uses the original anonymised Wiki Solar calibration table
from [Dunnett's Figshare archive, version 2](https://doi.org/10.6084/m9.figshare.11310269.v2).
All Spanish records are held out. Its predictor is an OSM polygon-area proxy,
which can include non-panel land. It cannot be substituted for detected pixel
area without separate calibration. The source reports MW without an AC/DC
declaration. Prediction intervals omit mapping uncertainty and domain shift.

The historical grouping profile implements settings in the original R scripts,
with explicit geometry validation and overlap safeguards. GHSL is epoch 2015,
release R2023A, sampled at grouped-farm centroids; that edition and sampling
differ from the original study. This workflow is not a reproduction of the
authors' complete historical inventory or their full pooled training data.

`reference_results.json` records the committed snapshot's measured results.
The weak-label transfer and capacity errors are substantial and are retained
as evidence, rather than hidden behind a high background-pixel accuracy.
