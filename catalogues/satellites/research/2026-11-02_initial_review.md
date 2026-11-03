# Initial spacecraft PV research review — 2 November 2026

Accepted 27 spacecraft/modules and 20 power-component model/configuration records
from 44 primary publisher sources. Scope spans astronomy, Earth observation,
communications, planetary science and technology demonstrations. Geography and
constellation coverage are incomplete; this batch is a foundation, not a global census.

## Acceptance decisions

- NASA/ESA mission ratings preserve their conditions. Psyche's 21 kW near Earth and
  2.3–3.4 kW asteroid range coexist. Rosetta keeps 850 W at 3.4 AU and 395 W at 5.25 AU.
- Bounds are retained: DART's ROSA design exceeds 6.6 kW BOL; Mars Express exceeds
  500 W at aphelion; Kepler's expected output is up to 1100 W. No bound becomes an
  exact nominal rating. MAVEN retains 1150–1700 W without an invented midpoint.
- Sentinel-2A/B use the explicit shared A/B design source; ratings are not treated
  as per-unit measured output and are not copied to C/D.
- Twenty components include size/configuration distinctions. AZUR 3G30/4G32 bare
  cells and CICs retain different efficiencies/currents. Rocket Lab Z4J+ electrical
  data is explicitly CIC with 100 µm coverglass. Spectrolab XTE-LILT's 31.6% at the
  1-AU reference is separate from a marketing 37% under distant LILT conditions.
- Documented links: DART → its ROSA array system; Europa Clipper → its Airbus array
  system; SPACE HAUC → EnduroSat 3U panels, GomSpace BP4 and P31u. No other
  spacecraft-to-OEM assignments are inferred.
- Clipper's 700 W is a design requirement near Jupiter, not measured output.
  SPACE HAUC's per-panel 8.5 W is not multiplied into spacecraft capacity without
  simultaneous illumination evidence. Exact Clipper AZUR cell model remains unknown.

## Conflicting or insufficient assertions

| Subject | Evidence issue | Admission decision |
| --- | --- | --- |
| Hubble | NASA gives approximately 5000 W and greater than 5200 W | Keep both qualified assertions; no preferred scalar |
| AstroSat | ISRO overview approximately 2000 W versus URSC 2100 W | Retain both; no average or preferred scalar |
| TESS | HEASARC 415 W, archived summary 433 W, writers guide 390 W | Keep three source-specific assertions; seek common phase/conditions |
| GOSAT | JAXA EORC 3.8 kW EOL versus SatNavi 3.3 kW EOL | Preserve conflicting spacecraft-power statements; no PV scalar |
| Cartosat-1 | ISRO page 15 m² versus bulletin 5 m² | Keep agreeing 1100 W, withhold array area |
| GSAT-11 | 13.6 kW labeled spacecraft power | Separate ambiguous-power column; PV remains null |
| EOS-04 / ALOS-2 | Generated power stated but PV measurement boundary not explicit | Store reported spacecraft power pending subsystem evidence |
| Solar Orbiter | 180 W is payload consumption | Do not use it as PV capacity |
| BepiColombo MTM | 2018 ESA propulsion-support figure up to 11 kW; later paper says 13 kW peak | Both source-specific ratings retained; preferred scalar withheld |
| AZUR 4G32 | Coverglass area 31.42 vs 31.34 cm² inside same document | Retain active cell area only; no coverglass-area assertion |

## Retrieval limits

The source registry gives exact URLs, dates and known revisions. Online pages/PDFs
or indexed primary-source excerpts were inspected; full raw documents were not
archived and document SHA-256 fields remain null. The Lockheed Martin Juno direct
page returned 403, but its indexed manufacturer excerpt supplied the approximate
500 W / greater-than-14 kW design statements. The NRSC EOS-04 handbook was too large
for the web retrieval tool; no unseen table values were admitted. The old GomSpace
P110 URL returned 404; no P110 record was admitted from a third-party substitute.

No current operational statuses, full NORAD/COSPAR identity crosswalk, live orbital
positions, inferred power totals or research recurrence were added. The offline OMM
stager prepares identity candidates only. New studies should deepen individual
records and regional/OEM coverage instead of inflating counts with family templates.

The validation suite checks unit/condition contracts, field/source provenance,
identity collisions, component links, unknown preservation, deterministic exports,
wheel data inclusion, and browser filtering/export behavior. See the PR for the
executed test/build results; this document does not certify hardware performance.
