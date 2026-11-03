# Lunar example input bundle

These are **inputs**, not measured lunar PV outputs. `provenance.json` records
original and extracted hashes. `analysis/lunar_surface_pv/fetch_inputs.py`
recreates the bundle using public connectors and a checked download cache.

| Files | Meaning |
| --- | --- |
| `site*_5m.npz` | Native 5 m pixel-centre windows from NASA PGDA site DEMs, elevations in metres. |
| `site*_80m.npz` | Native 80 m regional windows, 40 km wide. |
| `regional_1280m.npz` | Every 16th native pixel from the broad 80 m DEM; omitted peaks remain a limitation. |
| `*_ephemeris.csv` | Computed Sun/Earth positions in MOON_ME_DE421, UTC and elapsed ET seconds. Year 2026 at 2 h; July 1--31 at 30 min. |
| `diviner_subset.tab`, `diviner_label.xml` | Original header, verbatim selected rows and unmodified PDS4 label; label count describes the full product. |
| `svs_metadata.json`, `svs_2026.jpg` | Unmodified NASA SVS metadata/overview illustration, not georeferenced flux data. |

The compact terrain windows retain original float32 heights and pixel centres;
they do not claim improved resolution or gap-filled measurements. NPZ readers
disable pickle. The source XML and TAB retain CRLF bytes.

Credits: NASA GSFC / Michael Barker and LOLA team (PGDA products 78 and 90);
NASA PDS / LRO Diviner / Jean-Pierre Williams and UCLA; NASA NAIF/JPL DE421;
NASA Scientific Visualization Studio / Ernie Wright (SVS 4930). Cite the original
datasets and publications listed in the modelling guide. Source material keeps
its original attribution and terms; the repository software licence does not
relicense third-party source material or imply NASA endorsement.
