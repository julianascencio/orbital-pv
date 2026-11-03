"""Evidence-backed spacecraft and space-power component catalogues.

JSONL is canonical; Parquet and browser JSON are reproducible derived snapshots.
No network requests, live positions, telemetry or model estimates are implicit.
"""

from .core import (
    CatalogueError,
    build_snapshot,
    coverage,
    load_records,
    load_schema,
    load_sources,
    merge_records,
    record_id,
    stage_omm,
    validate_catalogue,
    validate_records,
)

__all__ = [
    "CatalogueError",
    "build_snapshot",
    "coverage",
    "load_records",
    "load_schema",
    "load_sources",
    "merge_records",
    "record_id",
    "stage_omm",
    "validate_catalogue",
    "validate_records",
]
