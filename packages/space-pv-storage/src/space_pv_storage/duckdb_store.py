from collections.abc import Iterable
from pathlib import Path
from typing import Any

import duckdb


class DuckDBStore:
    """Local analytical store for telemetry, derived features and lab outputs.

    DuckDB is deliberately kept separate from operational job metadata. It is the
    lightweight default for notebooks, batch research and reproducible local labs.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def initialize(self) -> None:
        with self.connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    satellite_id VARCHAR NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    source VARCHAR NOT NULL,
                    signal VARCHAR NOT NULL,
                    value DOUBLE,
                    unit VARCHAR,
                    quality VARCHAR,
                    ingested_at TIMESTAMPTZ DEFAULT current_timestamp
                )
                """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS derived_metrics (
                    satellite_id VARCHAR NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    metric VARCHAR NOT NULL,
                    value DOUBLE,
                    unit VARCHAR,
                    model_version VARCHAR,
                    run_id VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT current_timestamp
                )
                """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_rollups (
                    satellite_id VARCHAR NOT NULL,
                    signal VARCHAR NOT NULL,
                    bucket_seconds INTEGER NOT NULL,
                    bucket_start TIMESTAMPTZ NOT NULL,
                    min_value DOUBLE,
                    max_value DOUBLE,
                    avg_value DOUBLE,
                    last_value DOUBLE,
                    sample_count BIGINT NOT NULL,
                    PRIMARY KEY (satellite_id, signal, bucket_seconds, bucket_start)
                )
                """)

    def insert_telemetry(self, rows: Iterable[dict[str, Any]]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        self.initialize()
        values = [(row["satellite_id"], row["timestamp"], row["source"], row["signal"], row.get("value"), row.get("unit"), row.get("quality")) for row in payload]
        with self.connect() as con:
            con.executemany("""
                INSERT INTO telemetry
                (satellite_id, timestamp, source, signal, value, unit, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, values)
        return len(values)

    def refresh_telemetry_rollup(self, satellite_id: str, signal: str, bucket_seconds: int = 60) -> None:
        """Build a compact min/max/avg/last cache for fast chart rendering."""
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds must be positive")
        self.initialize()
        with self.connect() as con:
            con.execute("DELETE FROM telemetry_rollups WHERE satellite_id = ? AND signal = ? AND bucket_seconds = ?", [satellite_id, signal, bucket_seconds])
            con.execute("""
                INSERT INTO telemetry_rollups
                SELECT
                    satellite_id,
                    signal,
                    ?,
                    to_timestamp(floor(epoch(timestamp) / ?) * ?) AS bucket_start,
                    min(value),
                    max(value),
                    avg(value),
                    arg_max(value, timestamp),
                    count(*)
                FROM telemetry
                WHERE satellite_id = ? AND signal = ? AND value IS NOT NULL
                GROUP BY satellite_id, signal, bucket_start
                """, [bucket_seconds, bucket_seconds, bucket_seconds, satellite_id, signal])
