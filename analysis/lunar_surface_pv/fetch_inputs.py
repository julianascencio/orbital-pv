"""Fetch public originals and rebuild compact, traceable offline lunar inputs.

Run from an installed checkout with orbital-pv[ground,orbit,examples]. Downloads
roughly 550 MB once; cached originals are checksum checked. No API keys required.
Original archives stay in --cache; derived subsets are written to --output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from orbitalpv import lunar
from space_pv_orbit.spice_engine import clear_kernels, load_kernels

ROOT = Path(__file__).resolve().parents[2]
SITES = {
    "01": (-11497.5, -12502.5),
    "04": (-2697.5, -6102.5),
    "11": (-37597.5, 14897.5),
}


def save_terrain(terrain: lunar.LunarTerrain, destination: Path) -> None:
    np.savez_compressed(
        destination,
        x_m=terrain.x_m,
        y_m=terrain.y_m,
        elevation_m=terrain.elevation_m.astype(np.float32),
    )


def prepare(cache: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    sources = []
    with lunar.LolaConnector(timeout_s=120) as connector:
        polar = connector.polar_dem(cache / "LDEM_80S_80MPP_ADJ.TIF")
        sources.append(polar)
        save_terrain(lunar.read_lola_geotiff(polar.path, stride=16), output / "regional_1280m.npz")
        for site, (x, y) in SITES.items():
            receipt = connector.site_dem(site, cache / f"Site{site}.tif")
            sources.append(receipt)
            fine = lunar.read_lola_geotiff(
                receipt.path, bounds_m=(x - 700, y - 700, x + 700, y + 700)
            )
            save_terrain(fine, output / f"site{site}_5m.npz")
            medium = lunar.read_lola_geotiff(
                polar.path, bounds_m=(x - 20000, y - 20000, x + 20000, y + 20000)
            )
            save_terrain(medium, output / f"site{site}_80m.npz")
    with lunar.DivinerConnector(timeout_s=120) as connector:
        data, label = connector.seasonal_temperature(1, cache / "diviner")
        sources.extend([data, label])
    selected = []
    total = 0
    with Path(data.path).open("rb") as stream:
        header = stream.read(68)
        for line in stream:
            total += 1
            x, y = float(line[0:9]) * lunar.MOON_RADIUS_M, float(line[11:20]) * lunar.MOON_RADIUS_M
            if any(abs(x - sx) <= 2000 and abs(y - sy) <= 2000 for sx, sy in SITES.values()):
                selected.append(line)
    subset = header + b"".join(selected)
    frame = lunar.parse_diviner_pcp(subset, Path(label.path).read_bytes(), allow_subset=True)
    (output / "diviner_subset.tab").write_bytes(subset)
    shutil.copyfile(label.path, output / "diviner_label.xml")
    with lunar.LunarSpiceConnector(timeout_s=120) as connector:
        kernels = connector.download(cache / "kernels")
        sources.extend(kernels)
    # This command owns its process and kernel pool; public methods never clear it.
    load_kernels([r.path for r in kernels])
    try:
        for name, start, stop, step in [
            ("year_2026", "2026-01-01", "2027-01-01", "2h"),
            ("month_2026", "2026-07-01", "2026-07-31", "30min"),
        ]:
            times = pd.date_range(start, stop, freq=step, tz="UTC")
            ephemeris = lunar.lunar_ephemeris(times.strftime("%Y-%m-%dT%H:%M:%SZ").tolist())
            ephemeris.to_csv(output / f"{name}_ephemeris.csv", index=False, float_format="%.10g")
    finally:
        clear_kernels()
    with lunar.LunarIlluminationConnector(timeout_s=60) as connector:
        metadata = connector.metadata(cache_path=cache / "svs_metadata.json")
        reference = connector.reference_image(2026, cache / "svs_2026.jpg")
        sources.extend([metadata.receipt, reference])
    shutil.copyfile(reference.path, output / "svs_2026.jpg")
    (output / "svs_metadata.json").write_bytes((cache / "svs_metadata.json").read_bytes())
    records = [
        {k: getattr(r, k) for k in ("source", "url", "retrieved_at", "sha256", "bytes")}
        for r in sources
    ]
    manifest = {
        "frame": lunar.LUNAR_FRAME,
        "sites": {
            key: {
                "x_m": x,
                "y_m": y,
                "selection": "Illustrative high point in PGDA site, not an approved landing location",
            }
            for key, (x, y) in SITES.items()
        },
        "sources": records,
        "transformations": {
            "terrain": "Native pixel centres; 5 m 1.4 km windows, 80 m 40 km windows, whole polar DEM strided by 16 (1280 m); no smoothing or gap filling",
            "diviner": f"Original header and {len(frame)} verbatim rows of {total}; x/y within 2000 m of any site; original XML retained; L_s 0--60 and subsolar longitude 0--15 deg; compiled 2009--2020",
            "geometry": "SPICE DE421 geometric Sun/Earth vectors in MOON_ME_DE421; UTC labels and ET elapsed seconds; 2h year and 30min month boundaries",
            "svs": "Unmodified NASA metadata and reference JPEG; qualitative illustration only",
        },
        "files": {},
    }
    for p in sorted(output.iterdir()):
        if p.is_file() and p.name not in {"provenance.json", "README.md"}:
            manifest["files"][p.name] = {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "examples/lunar/_data")
    args = parser.parse_args()
    manifest = prepare(args.cache, args.output)
    print(f"Wrote {len(manifest['files'])} provenance-tracked offline input files")
