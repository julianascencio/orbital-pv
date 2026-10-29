# Space PV cells, arrays and specific power

_Last reviewed: 2026-09-09_

## 1. Flight baseline: III-V multijunction

III-V multijunction technology remains the benchmark for high-performance spacecraft power. NASA's 2026 survey places current space cell technology at 3–5 junctions, nominally around 30% efficiency and up to roughly 34% in the surveyed state-of-the-art range. Commercial and flight architectures include conventional triple junction, four-junction and inverted-metamorphic variants.

For analytics, the important point is that a multijunction cell is **series-current-limited across subcells**. A single broadband effective-irradiance number can therefore miss spectral mismatch effects. The long-term model architecture should support:

```text
AM0 spectrum
   ↓
spectral response per junction
   ↓
Jsc_junction(t)
   ↓
current matching / tunnel junctions
   ↓
cell I-V
```

The initial pvlib adapter remains useful as a reference and validation scaffold, but it should not become the final multi-junction physics implementation.

## 2. Inverted metamorphic and higher-junction cells

Recent reviews identify inverted metamorphic multijunction (IMM) architectures as one of the most advanced III-V approaches because lattice-mismatched materials allow a better bandgap stack than strict lattice matching. The trade is fabrication complexity, fragile epitaxial structures and cost. Epitaxial lift-off and substrate reuse remain important manufacturing research areas.

**Analytics implication:** the repository should model technology families by physical parameters and measured BOL/EOL curves, not hard-code a single "space cell" efficiency.

## 3. Flexible arrays and array-level metrics

The current array problem is not only photovoltaic conversion. Mission trades depend on:

- array specific power `W/kg`;
- areal power `W/m²`;
- stowed volume;
- deployment reliability;
- articulation/pointing capability;
- harness and interconnect losses;
- thermal properties;
- radiation/atomic-oxygen/UV durability.

NASA's 2026 SmallSat survey explicitly emphasizes specific power and shows that EOL performance at operating temperature is a critical metric. Flexible-array literature likewise treats cell, blanket, substrate and deployment structure as one system.

This suggests a technology object such as:

```python
SpacePVTechnology(
    cell_family=...,
    bol_efficiency=...,
    array_specific_power_w_kg=...,
    areal_density_kg_m2=...,
    temp_coefficients=...,
    radiation_model=...,
    coverglass=...,
    deployment_class=...,
)
```

## 4. Thin-film flight evidence

The AlSat-1N Thin-Film Solar Cell experiment is a key open reference because it reports **six years of spaceflight results** for lightweight CdTe devices. Long-duration flight evidence is much more valuable for this repository than isolated efficiency records because it gives a basis for degradation-model validation.

A separate 2026 CubeSat deployable-array paper reports a rigid-flex PCB architecture with flight testing, illustrating that array mechanics and packaging remain active innovation areas even when the cell technology itself is mature.

## 5. Perovskites: now an in-orbit research technology

Perovskites are compelling because of very high theoretical/experimental specific power, flexible processing and radiation tolerance. The 2024–2026 literature has shifted the evidence level:

- rollable/printed devices have been developed for LEO-relevant deployment concepts;
- radiation and thermal-shock protocols are becoming more realistic;
- SSPD-1 provided real LEO measurements over many eclipse cycles;
- ISS/MISSE experiments exposed complete devices and films to sustained LEO conditions.

The key caution is that absorber stability alone is not sufficient. In-flight/post-flight results point to **contacts, interfaces, ion migration, encapsulation and pre-flight storage/exposure** as critical failure modes.

Therefore a perovskite model should eventually separate:

```text
absorber degradation
contact/interface degradation
encapsulation / optical loss
thermal-cycle damage
radiation response
```

instead of fitting one efficiency-retention curve.

## 6. Ultrathin silicon deserves a branch

A 2026 open-access study on ultra-thin silicon heterojunction devices argues for a renewed space role based on high specific power, radiation behavior and partial recovery with annealing. This is strategically relevant because a lower-cost technology with excellent `W/kg` can beat a higher-efficiency cell in some SmallSat mission trades.

## 7. Recommended technology tiers for the lab

### Tier A — reference / near-term
- triple-junction III-V / GaAs-family array;
- generic 4J/IMM parameter set;
- simplified silicon reference.

### Tier B — flight-research technologies
- CdTe thin film (AlSat-1N-informed);
- perovskite (SSPD-1 / MISSE-informed);
- ultrathin silicon heterojunction.

### Tier C — exploratory
- perovskite/III-V tandem;
- perovskite/Si tandem;
- CIGS flexible arrays;
- 2D-material ultralight devices.

## Open / public references

- NASA 2026 Power SoA: https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
- **Space Photovoltaics: Materials, Device Concepts and Operational Challenges** (2026, OA): https://www.mdpi.com/2079-9292/15/10/1978
- **Advances in multijunction solar cells: An overview** (2025, OA): https://doi.org/10.1016/j.seja.2025.100105
- **Six years of spaceflight results from the AlSat-1N Thin-Film Solar Cell experiment** (2023, OA): https://doi.org/10.1016/j.actaastro.2023.08.034
- **Toward Rollable Printed Perovskite Solar Cells for Deployment in LEO Space Applications** (2024, OA): https://doi.org/10.1021/acsaem.3c02761
- **Towards space compatible perovskite solar cells: guidelines for thermal shock resilience and near space balloon testing** (2026, OA): https://doi.org/10.1039/D5EE03704B
- **Beyond Earth: Resilience of Quasi-2D Perovskite Solar Cells in Space** (2026, open repository copy): https://authors.library.caltech.edu/records/9brt4-5mb24
- **Silicon's cosmic comeback: Temperature-dependent performance and radiation stability of ultra-thin silicon heterojunction solar cells for space applications** (2026, OA): https://doi.org/10.1016/j.mtener.2026.102245
- **Design and performance of a compact rigid-flex PCB-based deployable solar array for cube satellites** (2026, OA): https://doi.org/10.1016/j.actaastro.2025.10.046
