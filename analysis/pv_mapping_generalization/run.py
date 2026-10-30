"""Offline geographic transfer comparison on licensed cached Sentinel-2 scenes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import orbitalpv as opv
from orbitalpv.ground_research import (
    ANDPI_SOURCE,
    SegmentationAdapter,
    adaptive_andpi,
    andpi_index,
    benchmark_segmentation,
    supervised_segmentation_adapter,
)


def run(data: Path, output: Path) -> dict:
    """Fit in Cestas, evaluate in Tenerife, and write raw provenance and metrics."""
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose an empty analysis output directory")
    configuration = json.loads((data / "pv-sites.json").read_text())
    sites = {
        name: opv.load_pv_site(
            **configuration[name],
            cache_dir=data,
            offline=True,
            assets=("scl", *opv.PV_SPECTRAL_BANDS),
        )
        for name in ("cestas", "tenerife")
    }
    samples = {
        name: opv.prepare_pv_training_sample(site, site_id=name, background_is_negative=True)
        for name, site in sites.items()
    }
    models = [
        supervised_segmentation_adapter([samples["cestas"]], method=method, random_state=0)
        for method in ("logistic", "random_forest")
    ]
    models.extend(
        [
            SegmentationAdapter(
                "fixed_NDPI_0",
                andpi_index,
                threshold=0.0,
                metadata={
                    "implementation": "fixed zero-index threshold baseline; not adaptive ANDPI",
                    "source": ANDPI_SOURCE,
                },
            ),
            SegmentationAdapter(
                "ANDPI_full_scene_adaptation",
                adaptive_andpi,
                metadata={"implementation": "paper adaptive rule without prior-inventory fusion"},
            ),
        ]
    )
    report = benchmark_segmentation(models, [samples["tenerife"]])
    report.update(
        data_kind="real cached Sentinel-2 imagery and OSM weak reference",
        labels="OSM generator polygons; outside buffered polygons explicitly assumed negative; absence may be incomplete",
        date_alignment="OSM snapshot 2026-10-30 versus scenes at their acquisition dates; no survey synchrony claimed",
        license="Copernicus Sentinel data terms; OpenStreetMap ODbL attribution",
        configuration={name: configuration[name] for name in sites},
        source_checksums={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(data.iterdir())
            if p.is_file()
            and p.name.startswith(("cestas", "tenerife"))
            and p.suffix in {".tif", ".json"}
        },
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    table = pd.DataFrame(
        [
            {k: v for k, v in row.items() if k != "prediction_provenance"}
            for row in report["results"]
        ]
    )
    table.to_csv(output / "heldout_metrics.csv", index=False)
    reference = samples["tenerife"]
    fig, axes = plt.subplots(1, len(models) + 1, figsize=(16, 3.5), constrained_layout=True)
    axes[0].imshow(
        np.ma.masked_less(reference.labels, 0),
        vmin=0,
        vmax=1,
        cmap="Greys",
        interpolation="nearest",
    )
    axes[0].set_title("OSM weak reference")
    for ax, model, row in zip(axes[1:], models, report["results"], strict=True):
        prediction = model.predict(reference.features)
        ax.imshow(prediction.mask, vmin=0, vmax=1, cmap="Greys", interpolation="nearest")
        ax.set_title(
            f"{model.name}\nF1 {row['f1']:.3f}"
            if row["f1"] is not None
            else f"{model.name}\nF1 undefined",
            fontsize=9,
        )
        np.savez_compressed(
            output / f"{model.name}.npz",
            scores=prediction.scores.filled(np.nan),
            mask=prediction.mask.filled(False),
            valid=~np.ma.getmaskarray(prediction.mask),
        )
    for ax in axes:
        ax.set_axis_off()
    fig.suptitle("Cestas-trained models transferred to Tenerife; no target-label tuning")
    fig.savefig(output / "geographic_transfer.png", dpi=160)
    plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "examples/ground_imagery/_data",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/pv_mapping_generalization"))
    args = parser.parse_args()
    result = run(args.data, args.output)
    print(
        json.dumps(
            [
                {
                    k: row[k]
                    for k in ("model", "f1", "iou", "precision", "recall", "relative_area_bias")
                }
                for row in result["results"]
            ],
            indent=2,
        )
    )
