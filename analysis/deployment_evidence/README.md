# Solar-array deployment evidence planning

ESA published [CRISTAL deployment testing](https://www.esa.int/media/about-us/directorates/earth-observation-programmes/copernicus/testing-cristal-s-solar-panel-deployment)
on **October 26, 2026**, 14 days before this November 9 review. The test event's
exact date is not supplied. The article reports integrated arrays and testing
at Airbus, but no trial counts or statistical reliability. This workflow does
not infer CRISTAL reliability, certification, or a deficiency in its programme.

## Business decision and scope

Customer: an array supplier's test manager and the mission assurance team.
Decision: how much independent hardware evidence is needed before making a
specified per-unit deployment reliability claim? Baseline: a small successful
campaign summarized by its observed pass fraction. KPI: exact one-sided lower
confidence bound, and the minimum fixed zero-failure sample count for a target.
Constraints: representative independent units, unchanged design, comparable
protocol, complete binary outcomes and predeclared sample size. Business value:
expose evidence gaps before committing manufacturing/test resources or making
unsupported procurement claims. No prices, expected mission revenue, or actual
ESA acceptance requirements are assumed.

The review found no open PRs and #37 already merged. Existing procurement,
monitoring and power-service methods do not estimate deployment confidence.
Current news also included NASA's November 5 final IROSA installation (already
covered by the array-power case), JAXA's October 30 update on September 10 bus
power delivery (covered by monitoring), and DOE's August 31 radiation/cell
manufacturing programme. Lunar/Mars and space-based solar scans did not provide
a stronger verified numerical-data story; SBSP delivery is already covered by
#37. A secondary November 8 lunar-contract report was not used because primary
confirmation was not established in this review.

News/context URLs, retrieved November 9, 2026:

- https://www.nasa.gov/blogs/spacestation/2026/11/05/spacewalkers-install-final-roll-out-solar-array/
- https://www.ihub-tansa.jaxa.jp/english/topics_Origamisat2_en.html
- https://www.energy.gov/cmei/articles/does-office-critical-minerals-and-energy-innovation-announces-first-major-investment
- https://www.nasa.gov/news-release/nasa-calls-for-proposals-to-accelerate-lunar-surface-technologies/ (September 8 solicitation, not November awards)

## Data and methods

The existing free-access `orbitalpv.data.load_table` connector loads an original
CSV with **40 synthetic one-shot hardware outcomes**: 20/20 successes in an
ambient protocol and 19/20 in a thermal-vacuum protocol. These are illustrative
records, not measurements, digitized ESA data or a test standard. The manifest
records source dates, rights and assumptions. No article text or imagery is
redistributed. No new mission endpoint or dependency was needed.

`orbitalpv.qualification.summarize_deployment_trials` checks identifiers and
binary outcomes, rejects repeated hardware in the same design/protocol, and
keeps protocols/designs separate. Unique identifiers cannot prove independence:
shared manufacturing defects, repeated use of an assembly, common test equipment
and environment mismatch require engineering review. Reusing a unit across
protocols does not make the two groups independent of each other; we do not
combine their evidence. Missing/censored outcomes must not be encoded as passes.

For s successes and f failures, n=s+f, the exact one-sided lower bound L solves
`P(F <= f | success probability=L) = 1-confidence`. The implementation uses a
log-space binomial tail and bisection. With zero failures, `L=(1-confidence)^(1/n)`;
with zero successes, L=0. Confidence is repeated-sampling coverage, not a
posterior probability that a particular spacecraft will deploy.

The smallest predeclared zero-failure campaign is
`ceil(log(1-confidence)/log(target_reliability))`. Floating-point integer
boundaries are checked. It is not valid to keep testing until this fixed-sample
interval crosses a threshold without accounting for sequential selection.

Method: [NIST exact binomial limits](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm).
Tests compare against independent SciPy beta quantiles for the Clopper-Pearson
bound: [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).
SciPy is used only as a validation oracle, already available in the repository's
ground dependency group; production methods use the standard library and pandas.
The NAVSEA handbook URL found during research returned HTTP 403 and was not used
as the implementation's retrieved methodological source.

## Executed findings and limitations

At 95% confidence, 20/20 successes yield a lower bound **0.860892**; 19/20 yield
**0.783894**. These bounds are for different illustrative protocols and must not
be interpreted as a measured environmental effect.

| Target per-unit reliability | Independent zero-failure units at 95% confidence |
|---|---:|
| 95% | 59 |
| 99% | 299 |
| 99.9% | 2,995 |

The 16-plan sensitivity grid crosses four targets (90/95/99/99.9%) with four
confidence levels (80/90/95/99%). The figure also compares zero, one and two
failures at fixed total sample sizes. Higher confidence/targets require more
units. For costly flight hardware, this exposes the limits of purely statistical
demonstration; it does not recommend manufacturing thousands of spacecraft.
Physics, fault-tree/common-cause analysis, qualification margins, process control
and relevant heritage remain necessary complementary evidence.

No lifetime model, radiation degradation attribution, accelerated-test equivalence,
independence verification, multi-array spacecraft reliability, or certification
is provided. One-shot deployment success is not sustained PV performance. Exact
binomial intervals address sampling uncertainty only; design/environment bias
and correlated failures can dominate it. No synthetic records are called measured.

## Reproduce

Python 3.13+, existing pandas/NumPy/Matplotlib; PyArrow for runner Parquet output:

```bash
uv sync --all-packages --group dev --group lab --group docs --group ground
PYTHONPATH=src MPLBACKEND=Agg uv run python analysis/deployment_evidence/run.py
PYTHONPATH=src MPLBACKEND=Agg uv run python examples/space_business/plot_deployment_evidence.py
uv run pytest tests/test_qualification.py
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
MPLBACKEND=Agg uv run sphinx-build -W --keep-going -b html docs/sphinx/source docs/sphinx/build/html
uv build
uv run twine check dist/*
```

Outputs under `outputs/deployment_evidence`: config, checksum-bearing input
manifest, metrics, logs, evidence.csv, plans.csv, events.parquet (grouped outcome
summaries) and figures/evidence.png. No random generation; seed is null. The
committed `reference_results.json` contains the executed values. The gallery
registers `examples/space_business/plot_deployment_evidence.py` automatically;
the research index and API reference expose it. Original synthetic data and code
use the repository license; referenced sources retain their own rights.

Local validation on November 9: 830 Python tests, repository Ruff and type checks,
web lint/tests/build, package build/Twine and four catalogue JavaScript tests
passed. The strict Sphinx build executed all 58 gallery examples successfully;
the new example also ran against an isolated installed wheel. Remote CI status
is recorded in the pull request separately, so local success is not confused
with missing remote checks.
