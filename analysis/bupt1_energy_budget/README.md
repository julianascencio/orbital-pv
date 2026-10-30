# BUPT-1 measured energy budget

This executable analysis downloads or consumes the pinned public
[SatelliteCOTS](https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS)
archive and reconciles measured MPPT output, bus load and battery power over
common valid intervals. It also keeps PV-side input power separate.

```bash
python analysis/bupt1_energy_budget/run.py \
  --archive /tmp/orbitalpv-bupt1/telemetry_all.csv.zip --download
```

The archive is pinned to commit
`951b41521351d535b7c2354916d9c4991602e8c7`, SHA-256
`5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa`.
It is about 81 MB compressed. The loader streams the CSV and never extracts
archive paths to disk. Its verified common-file schema provides per-MPPT
input/output values; the separately supported short-term schema is multiplexed
and deliberately requires independent channel alignment before whole-bus use.

The default six-hour interval has 21,598 native records from 09:00 to 15:00 on
5 May 2023; 7,349 records have nonzero computing currents. Median native
cadence is one second and the integration cutoff admits two-second intervals. The
source's timezone is unspecified: these are **source-local clock labels**,
not established UTC. Relative time integration does not require an assumed
UTC offset. To align external ephemerides, supply a separately established
timezone and aware time bounds. Zero temperature and signed currents remain
unchanged. Duplicate clocks, if present, are excluded rather than averaged.

The source repository has no explicit redistribution licence, so this repo
commits **aggregate numerical results only**, not raw BUPT-1 files. Reproduce
the aggregates in `reference_results.json` from the original pinned download.
The offline gallery displays those precomputed measured aggregates and labels
them accordingly. Source: [MobiCom 2024 paper](https://arxiv.org/abs/2401.03435).

The residual includes measurement timing/calibration, unmodelled branches and
boundary discrepancies. It is not automatically conversion loss or PV aging,
and observed V×I does not establish available maximum power.
