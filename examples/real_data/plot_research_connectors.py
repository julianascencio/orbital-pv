"""
Free spacecraft research APIs: evidence, archives and geometry
==============================================================

Use seven anonymous APIs through the public OrbitalPV interface, replaying
small original responses captured on 3 November 2026. Each replay verifies the
exact request and SHA-256. This example performs no network requests: missing
snapshots raise an error. To run new live queries, use the opt-in
``scripts/check_research_connectors.py`` script from an installed checkout.

NASA reports supply specification evidence; Zenodo/Dataverse discover research
datasets; PDS/PSA discover mission products; Horizons supplies geometry; DONKI
supplies event context. These are distinct inputs. No discovered report or
dataset is automatically assigned a PV capacity. DISCOS is demonstrated in the
user guide because it needs an explicit free-account token.

Attribution and provider documentation are retained in each response and its
sidecar. See ``_research/README.md`` for source-specific scope and usage notes.
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import orbitalpv as opv

# %% Read original report and dataset metadata

directory = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
cache = directory / "_research"
for source in ("ntrs", "zenodo", "dataverse", "horizons", "pds", "psa", "donki"):
    for suffix in (".json", ".json.provenance.json"):
        if not (cache / f"{source}{suffix}").is_file():
            raise FileNotFoundError("Run this example from a checkout with its _research snapshots")

with opv.NtrsConnector() as api:
    papers = api.search('"solar array" "end of life"', page_size=5, cache_path=cache / "ntrs.json")
print("Report discovery — review the original documents before accepting specifications:")
for paper in papers.data["results"]:
    print(f"  {paper['id']}: {paper['title']}")
print(f"This page has {len(papers.data['results'])} of {papers.data['stats']['total']} hits.")

with opv.ZenodoConnector() as api:
    zenodo = api.record(15108715, cache_path=cache / "zenodo.json")
print("Zenodo:", zenodo.data["metadata"]["title"], zenodo.data["doi"])
print("Available files:", [file["key"] for file in zenodo.data["files"]])

with opv.DataverseConnector() as api:
    description = api.dataset(
        "doi:10.18419/darus-456", version="1.0", cache_path=cache / "dataverse.json"
    )
print(
    "Flying Laptop packet/units description:",
    description.data["data"]["files"][0]["dataFile"]["filename"],
)

# %% Resolve mission-product metadata without treating it as EPS telemetry

with opv.PdsConnector() as api:
    pds = api.search('(product_class eq "Product_Bundle")', limit=2, cache_path=cache / "pds.json")
print("PDS bundles in this bounded page:", [row["id"] for row in pds.data["data"]])

with opv.PsaConnector() as api:
    psa = api.query(
        "SELECT TOP 2 granule_uid, instrument_host_name, access_url "
        "FROM psa.epn_core WHERE instrument_host_name = 'Mars Express'",
        max_records=2,
        cache_path=cache / "psa.json",
    )
print("PSA columns:", [column["name"] for column in psa.data["metadata"]])
print("PSA first product:", psa.data["data"][0])

# %% Inspect the original Juno ephemeris and a geometric illumination factor
#
# This narrowly scoped example reads VEC_TABLE=2 CSV rows between Horizons'
# data markers. We retain TDB date strings rather than converting them to UTC.
# Squared inverse Sun distance gives an illustrative illumination scaling
# relative to 1 AU. It is not measured irradiance or predicted array wattage.

with opv.HorizonsConnector() as api:
    geometry = api.vectors(
        "-61", start="2024-01-01", stop="2024-01-04", cache_path=cache / "horizons.json"
    )
body = geometry.data["result"].split("$$SOE", 1)[1].split("$$EOE", 1)[0]
rows = [row for row in csv.reader(body.strip().splitlines()) if row]
date_labels = [row[1].strip().split()[1] for row in rows]
positions_au = np.array([[float(value) for value in row[2:5]] for row in rows])
distance_au = np.linalg.norm(positions_au, axis=1)
illumination_fraction = 1.0 / distance_au**2

fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
ax.plot(date_labels, 100 * illumination_fraction, marker="o", color="#2563eb")
ax.set(
    ylabel="Geometric sunlight factor (% of 1 AU)",
    xlabel="Ephemeris date (TDB)",
    title="Juno: inverse-square scaling from JPL Horizons vectors",
)
ax.ticklabel_format(axis="y", style="plain", useOffset=False)
ax.grid(alpha=0.25)
print(f"Juno Sun distance: {distance_au.min():.6f}-{distance_au.max():.6f} AU")
print("Original API signature:", geometry.data["signature"])

# %% Read space-weather context from a separate historical window
#
# These May 2024 flares are not aligned to the January Juno plot and do not
# establish a spacecraft power anomaly, local dose, or degradation rate.

with opv.DonkiConnector() as api:
    donki = api.events(
        "FLR", start="2024-05-10", stop="2024-05-11", cache_path=cache / "donki.json"
    )
events = donki.data or []
print("DONKI flare records, 10-11 May 2024:", len(events))
print("Example event:", events[0]["beginTime"], events[0]["classType"], events[0]["link"])
print("Source response SHA-256:", donki.receipt.sha256)
