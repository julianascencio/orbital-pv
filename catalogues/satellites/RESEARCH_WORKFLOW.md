# Research and update workflow

1. Start from current main and inspect open PRs. Work in an isolated branch. Preserve
   concurrent tracking, physics and imaging work; do not force-push another task.
2. Select a concrete mission/operator/OEM batch from the backlog. Prefer mission
   agencies, engineering teams, manufacturer datasheets and authored technical papers.
   Track unsuccessful sources and evidence gaps as carefully as accepted values.
3. Identify exact spacecraft, modules, OEM model and revision/configuration. Reuse an
   existing UUID even when adding NORAD/COSPAR identifiers. Screen aliases and identifiers;
   do not count a bus family as thousands of individually verified spacecraft.
4. Register the exact source URL, publisher, inspection date, document revision, reuse
   notes and SHA-256 when bytes have actually been retrieved. Do not invent hashes or
   claim to have retrieved a blocked document. Preserve old source IDs for old revisions.
5. Extract only supported facts. Attach source IDs to each populated field and add
   concise original evidence summaries with page/table/section locators. Keep
   source conditions and qualifiers; unknown remains null. Avoid full-document copying.
6. Power needs explicit attribution to PV generation. Keep consumption and ambiguous
   spacecraft power separate. Do not invent total watts from efficiency/area, nor multiply
   per-panel ratings without illumination evidence. Retain ranges and conflicting
   assertions separately; a scalar remains null when selecting one is unjustified.
7. Link component UUIDs to spacecraft only with direct installation evidence. A known
   cell manufacturer does not identify an exact model. Separate source-confirmed hardware
   from a synthetic simulation configuration.
8. Use `merge_records` to fill missing data and collect conflicts without overwriting
   existing assertions. Review conflicts manually; keep the discarded/superseded claim
   in the research ledger and Git history. Write sorted canonical records to the
   first-two-characters-of-UUID shard. This is a single-writer Git workflow.
9. Run `python -m orbitalpv.catalogue validate`, catalogue tests, JS tests, Ruff/ty,
   snapshot rebuild and Sphinx build. Check completeness changes and material scientific
   distinctions. Generated binary snapshots are build outputs, not committed data.
10. Open/update a scoped PR with additions, enrichment, unresolved gaps, evidence URLs
    and actual validation results. Merge/publication follows the user's authorization.

## Expansion priorities

- Starlink, OneWeb and Kuiper: official model/generation distinctions, FCC filings,
  supplier evidence, individual IDs, actual rated array conditions. No mass-based W guesses.
- GEO communications and navigation: operator fleet pages, Airbus/Thales/Maxar/ISRO,
  Galileo/GPS/BeiDou, qualified EOL power and battery/controller details.
- Chinese, Japanese, Indian and other missions: original-agency technical specifications,
  exact translations and mission-phase labels. Do not generalize regional designs.
- Space stations and upgrades: time/configuration-specific arrays, preventing old and
  upgraded capacity from being summed as separate complete stations.
- Small spacecraft: mission team inventories plus exact EPS, batteries, panels and cells.
- OEMs: additional AZUR sizes and revisions, CESI, DHV, Spectrolab XTE+ LEO, deployables,
  PCDUs, battery chemistries, EOL irradiation fluence, temperature coefficients and mass.
- Reconcile Hubble, AstroSat, TESS, GOSAT and Cartosat-1 source differences before
  selecting previously withheld preferred figures.

CelesTrak/OMM is an identity/ephemeris source, not a PV specification source. The
`stage-omm` command accepts supplied JSON and emits review candidates only. Review
provider terms and register the downloaded byte hash before admission. Match candidates
against named mission aliases before adding any new spacecraft record.

This workflow is reusable but no recurring automation is enabled by adding it.
