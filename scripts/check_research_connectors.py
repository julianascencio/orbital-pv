"""Run small, explicit live queries against the free research APIs.

From an installed checkout: python scripts/check_research_connectors.py
Use --cache-dir to select the output directory. --discos additionally requires
DISCOS_TOKEN in the environment; it is never written to the output or receipts.
This script is opt-in and is not run by CI or documentation builds.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orbitalpv as opv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/research-connectors"))
    parser.add_argument("--discos", action="store_true")
    args = parser.parse_args()
    output = args.cache_dir
    output.mkdir(parents=True, exist_ok=True)
    queries: list[tuple[str, Callable[..., Any], Callable[[Any, Path], opv.ResearchResponse]]] = [
        (
            "ntrs",
            opv.NtrsConnector,
            lambda api, path: api.search(
                '"solar array" "end of life"', page_size=5, cache_path=path, refresh=True
            ),
        ),
        (
            "zenodo",
            opv.ZenodoConnector,
            lambda api, path: api.record(15108715, cache_path=path, refresh=True),
        ),
        (
            "dataverse",
            opv.DataverseConnector,
            lambda api, path: api.dataset(
                "doi:10.18419/darus-456", version="1.0", cache_path=path, refresh=True
            ),
        ),
        (
            "horizons",
            opv.HorizonsConnector,
            lambda api, path: api.vectors(
                "-61", start="2024-01-01", stop="2024-01-04", cache_path=path, refresh=True
            ),
        ),
        (
            "pds",
            opv.PdsConnector,
            lambda api, path: api.search(
                '(product_class eq "Product_Bundle")', limit=2, cache_path=path, refresh=True
            ),
        ),
        (
            "psa",
            opv.PsaConnector,
            lambda api, path: api.query(
                "SELECT TOP 2 granule_uid, instrument_host_name, access_url "
                "FROM psa.epn_core WHERE instrument_host_name = 'Mars Express'",
                max_records=2,
                cache_path=path,
                refresh=True,
            ),
        ),
        (
            "donki",
            opv.DonkiConnector,
            lambda api, path: api.events(
                "FLR", start="2024-05-10", stop="2024-05-11", cache_path=path, refresh=True
            ),
        ),
    ]
    if args.discos:
        token = os.environ.get("DISCOS_TOKEN", "")
        if not token:
            parser.error("--discos requires DISCOS_TOKEN")
        queries.append(
            (
                "discos",
                lambda **kw: opv.DiscosConnector(token=token, **kw),
                lambda api, path: api.by_norad(25544, cache_path=path, refresh=True),
            )
        )
    checks = []
    for name, factory, query in queries:
        try:
            with factory(timeout_s=60) as api:
                result = query(api, output / f"{name}.json")
            checks.append(
                {
                    "provider": name,
                    "status": "ok",
                    "bytes": result.receipt.bytes,
                    "sha256": result.receipt.sha256,
                    "request_url": result.request_url,
                }
            )
        except Exception as exc:
            # Do not print request headers or credentials, even on failure.
            checks.append({"provider": name, "status": "failed", "error_type": type(exc).__name__})
        print(json.dumps(checks[-1]), flush=True)
    report = {"checked_at": datetime.now(UTC).isoformat(), "checks": checks}
    (output / "access-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if any(check["status"] != "ok" for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
