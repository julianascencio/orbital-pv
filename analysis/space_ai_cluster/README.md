# Solar-powered AI satellite cluster study

This study connects the supplied **arXiv:2511.19468v2** paper to reusable
OrbitalPV methods, a version-pinned literature connector, an offline evidence
snapshot, nine reproducible analysis tables, and a runnable gallery example.

Source: Agüera y Arcas et al., *Towards a future space-based, highly scalable AI
infrastructure system design*, version dated June 17, 2026.
[Paper](https://arxiv.org/abs/2511.19468v2) ·
[arXiv API documentation](https://info.arxiv.org/help/api/user-manual.html).
The source PDF hash and numerical page locators are in
[`space_ai_2511_19468v2.json`](../../src/orbitalpv/_data/space_ai_2511_19468v2.json).
The paper's copyrighted text, figures and PDF are not redistributed.

## Run

From a source checkout with Python 3.13 or newer:

```bash
python -m pip install -e '.[examples]'
python analysis/space_ai_cluster/run.py --output outputs/space_ai_cluster
python examples/space_business/plot_space_ai_cluster.py
```

The default study and gallery are fully offline. To refresh **only bibliographic
metadata** for the pinned version:

```bash
python analysis/space_ai_cluster/fetch_metadata.py
```

The connector saves original Atom bytes, SHA-256, request URL and retrieval time.
It validates the response version, rejects malformed/provider-error feeds and
checks cache integrity. `--refresh` is explicit; reuse the cache and space live
requests by at least three seconds. PDF download is optional through
`ArxivConnector.download_paper`; it is not required by the study.

Change assumptions by copying the packaged JSON and passing `--input path.json`.
The output provenance embeds that exact input and its SHA-256. Input changes do
not update the paper's reported benchmark fields automatically.

## What was added

| Layer | API / artifact | Purpose |
|---|---|---|
| Connector | `orbitalpv.data.ArxivConnector` | Pin a paper version, cache metadata and optionally retrieve its PDF |
| Evidence adapter | `load_space_ai_evidence` | Load locally curated facts with locators, statuses and source hash |
| Optical method | `OpticalLinkSpec`, `optical_link_budget` | Friis power, photon ceiling, electronics cap, receiver margin and propagation latency |
| Near-field method | `confocal_spatial_geometry` | Ideal single/2×2/4×4 sub-aperture range and pointing allowance |
| Formation method | `FormationSpec`, `hcw_formation`, `formation_metrics` | Independent 81-member bounded HCW lattice and separation/link-distance metrics |
| Radiation method | `radiation_event_screen` | Conditional per-device/fleet event exposure, keeping SDC, UECC and SEFI separate |
| Economics | `launched_power_cost`, `launch_learning_price`, `launch_energy_cost_parity` | Recomputed proxy costs, Wright curves and partial electricity-cost parity |
| Integrated analysis | `space_ai_trade_study` | Compose new methods with existing eclipse, battery, solar and radiator constraints |
| Gallery | `plot_space_ai_cluster.py` | Six-panel offline comparison, included in the documentation gallery |

## Equations and boundaries

**Optics:** use the paper's Eq. 1 with `G = eta (pi D/lambda)^2` and
`Pr = Pt Gt Gr (lambda/(4 pi d))^2 10^(-loss_db/10)`. Photon-limited bit rate is
`Pr / (h c/lambda) / photons_per_bit`. A 24-channel electronics cap and an equal
power split among channels are explicit. A passed full-rate screen requires both
a nonnegative receiver margin and enough photons. A lower calculated ceiling
with negative full-rate margin does **not** prove a lower-rate modem mode works.
Distances below the conservative `2 D²/lambda` far-field boundary are rejected.

The paper uses mixed bandwidth wording: 800 Gbps one-way/1.6 Tbps aggregate for
the short bench experiment, but calls 24 × 400 Gbps = 9.6 Tbps bidirectional.
Our model adopts **400 Gbps per channel per direction as an explicit engineering
convention**. It preserves the reported wording separately and does not double
the paper's 9.6 Tbps claim or present it as measured in orbit.

**Near field:** the paper's `L = pi a²/lambda` gives ideal geometric distances
of 5.067, 1.267 and 0.317 km for 1×1, 2×2 and 4×4 subdivisions of a 10 cm aperture.
The ~0.987 microradian pointing allowance at 5.067 km assumes wander of 10% of
radius. This calculation omits beam quality, truncation, jitter and power sharing;
it provides no validated multiplexed throughput. It is not the far-field model.

**Formation:** `x=A cos(nt)+B sin(nt)`, `y=-2A sin(nt)+2B cos(nt)` solves the
bounded planar HCW equations in rotating LVLH coordinates. A 9×9 parameter
lattice is scaled to a maximum cluster radius of 1 km at 650 km altitude. Its
nearest grid-edge separations range from about 88 to 177 m, rather than claiming
the paper's approximate 100–200 m geometry is exactly reproduced. The paper's
2:1.0037 J2 adjustment, <3 m/s/year/km drift estimate, DOP853 simulations and
proposed differentiable control are contextual evidence, **not implemented or
validated control capabilities**. Sampled separation is not collision certification.

**Radiation:** annual event count is supplied dose rate / measured dose per event;
fleet mission expectation scales by device count and years. A constant-rate
Poisson screen gives `P(at least one event) = 1-exp(-expected events)`. Rates
are conditional on test device, workload and radiation spectrum. The source's
67 MeV is beam energy before intervening material, not monoenergetic die exposure.
No shielding/transport model is inferred from 10 mm Al, and no generic accelerator
qualification is claimed. TID observations and event rates remain separate.

**Costs:** launch-only annual cost is `mass × launch price / (power × lifetime)`;
Wright learning is `C=C0 (M/M0)^log2(1-LR)`. The 18%, 20% and 24% learning-rate
curves are assumptions. Cumulative mass has no automatic calendar mapping. The
Table 1 calculations retain both reported and independently calculated values.
Using its rounded Starlink v2 inputs gives $821.43/kW-year, while the paper reports
$810; the source estimate of 105 m² × 22% × 90% × 1361 W/m² gives 28.295 kW before
EPS/thermal/environmental losses. Neither number is an official hardware rating.

## Decision use and synthetic scenario

The integrated screen asks how much continuous compute electrical power survives
solar loss, eclipse storage and radiator constraints, and how that changes the
launch price at which **launch cost alone** equals terrestrial electricity spend.
It reuses `OrbitalComputeSpec` / `screen_orbital_compute` rather than maintaining
another power or thermal implementation.

The baseline assumes 20 kW compute, 2 kW platform, a 5 kWh battery, 80 m² total
radiator emitting area at 320 K, 90% array derate, 95% EPS efficiency and a 2.5 kW
thermal loss reserve. Beta=90° is a best-case geometry, not a year-round guarantee
from the SSO label. Other cases use beta=0°, half radiator area or 25% PV loss.
A 575 kg mass proxy, five-year life, $0.10/kWh, PUE 1.2 and 80% utilization are
explicit scenario assumptions. They are not a complete TPU spacecraft design.
The 81-device radiation aggregation assumes one device per satellite for
illustration; the paper does not specify that payload count.

Useful decisions include optical terminal range screening, memory/error-mitigation
research priorities, thermal versus PV sizing, and launch-cost sensitivity.
The result excludes spacecraft and chip acquisition, operations, repair,
replacement, insurance, financing, ground links, collective-network performance,
training checkpoint recovery, legal approvals and useful AI-work throughput.
Thus it cannot establish investment returns, overall economic parity or readiness.

## Outputs and validation

The runner writes `solar_estimate.csv`, `optical_links.csv`,
`spatial_geometry.csv`, `formation.csv`, `radiation_events.csv`, `tid_context.csv`,
`launched_power.csv`, `learning_curve.csv`, `compute_screen.csv` and
`provenance.json`. Checked-in reference results retain compact key values;
re-run the analysis to generate complete tables.

Tests verify independent published approximations, inverse-square scaling,
photon/power conservation, optical regime rejection, HCW periodicity and
finite-difference differential equations, radiation aggregation, launch-cost
hand calculations, source-version enforcement and cache tamper detection.
Live metadata availability is not required for CI.
