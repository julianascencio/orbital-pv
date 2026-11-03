# Satellite and space-power database

An OrbitalPV catalogue inspired by Energy Data Insights: one record per identifiable
spacecraft/module, one per exact OEM model or documented configuration, evidence per
field, Git-reviewable updates and reproducible typed Parquet exports.

The canonical data is **`src/orbitalpv/catalogue/data/`**, packaged with the wheel.
This directory holds research instructions and the evidence review; it is not a
competing data store. Two-character UUID shards in `data/records/{entity}/` contain
sorted JSONL, and `data/sources.json` is the registry of exact source documents.

Initial scope: **27 spacecraft, 20 components, 44 primary sources**. See
[the initial research review](research/2026-11-02_initial_review.md). This is not a
complete satellite inventory or a live-generation data feed.

```bash
python -m pip install ".[catalogue,examples]"
python -m orbitalpv.catalogue validate
python -m orbitalpv.catalogue build --output outputs/satellite-snapshot
```

The immutable snapshot contains two Parquet tables, two browser projections,
source registry, schema, attribution and hashes/coverage manifest. Browser JSON is
read back from Parquet; it is not independently edited. Documentation builds publish
these under `_static/satellite-db/` with an interactive `database-viewer.html`.

Full contracts: [user guide](../../docs/sphinx/source/user_guide/modeling_topics/satellite_catalogue.rst),
[field dictionary](../../src/orbitalpv/catalogue/data/schema.json),
[research workflow](RESEARCH_WORKFLOW.md).

Key distinctions:

- Preferred PV watts, alternative/range ratings and ambiguous spacecraft power.
- BOL, EOL and mission-reference conditions; Sun distance, temperature, irradiance.
- Cells versus CICs, named models versus mission-specific array configurations.
- Per-panel output versus total simultaneously illuminated spacecraft output.
- Battery Wh versus Ah, active cell area versus structural array area.
- Historical designs versus actual generation; source inspection versus flight validation.

No total across unlike ratings is presented. No current status, coordinates,
component installation or constellation-member power is inferred.
