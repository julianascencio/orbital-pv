"""Offline catalogue validation, conservative merging and snapshot exports."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

DATA_ROOT = Path(__file__).with_name("data")
METADATA = {
    "record_id",
    "identity_key",
    "entity_type",
    "created_at",
    "updated_at",
    "last_verified_at",
    "sources",
    "field_sources_json",
    "evidence_json",
    "quality_status",
    "notes",
}
QUALIFIERS = {"reported", "approximate", "lower_bound", "upper_bound"}
BASES = {"BOL", "EOL", "mission_reference", "unspecified"}


class CatalogueError(ValueError):
    """Invalid catalogue record, source or snapshot."""


def _json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def _root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else DATA_ROOT


def load_schema() -> dict:
    """Return the installed versioned field dictionary."""
    return json.loads((DATA_ROOT / "schema.json").read_text(encoding="utf-8"))


def load_sources(root: str | Path | None = None) -> dict:
    """Return source IDs mapped to exact URLs and retrieval/reuse metadata."""
    return json.loads((_root(root) / "sources.json").read_text(encoding="utf-8"))


def record_id(entity_type: str, identity_key: str) -> str:
    """Stable UUID5; preserve case, punctuation and explicit configuration identity."""
    return str(
        uuid5(NAMESPACE_URL, f"https://orbitalpv.org/catalogue/{entity_type}/{identity_key}")
    )


def load_records(entity_type: str | None = None, root: str | Path | None = None) -> list[dict]:
    """Read canonical records, sorted by UUID. Unknown fields remain absent/null."""
    entities = load_schema()["entity_types"]
    if entity_type is not None and entity_type not in entities:
        raise CatalogueError(f"Unknown entity type: {entity_type}")
    records = []
    for entity in [entity_type] if entity_type else entities:
        for path in sorted((_root(root) / "records" / entity).glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("entity_type") != entity:
                        raise CatalogueError(f"Wrong entity in {path}")
                    if path.stem != row.get("record_id", "")[:2]:
                        raise CatalogueError(f"Wrong identity shard in {path}")
                    records.append(row)
    return sorted(records, key=lambda row: row["record_id"])


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CatalogueError("Timestamps must be UTC ISO strings ending in Z")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogueError(f"Invalid timestamp: {value}") from exc


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _rating(rating: dict, sources: set[str]) -> None:
    required = {"power_w", "qualifier", "basis", "conditions", "source_id"}
    allowed = required | {"distance_au", "temperature_c", "irradiance_w_m2"}
    if not isinstance(rating, dict) or not required <= rating.keys() or rating.keys() - allowed:
        raise CatalogueError(
            "Power rating requires power_w, qualifier, basis, conditions, source_id"
        )
    if not _number(rating["power_w"]) or rating["power_w"] < 0:
        raise CatalogueError("Power must be a finite nonnegative number")
    if rating["qualifier"] not in QUALIFIERS or rating["basis"] not in BASES:
        raise CatalogueError("Unrecognized power qualifier or life basis")
    if not isinstance(rating["conditions"], str) or not rating["conditions"].strip():
        raise CatalogueError("Power rating needs reference conditions")
    if rating["source_id"] not in sources:
        raise CatalogueError("Power rating references an unregistered record source")
    for key in ("distance_au", "temperature_c", "irradiance_w_m2"):
        if key in rating and (
            not _number(rating[key]) or (key != "temperature_c" and rating[key] <= 0)
        ):
            raise CatalogueError(f"Invalid reference condition: {key}")


def validate_records(records: list[dict], sources: dict) -> None:
    """Validate types, units, identities, field evidence and cross-catalogue links.

    Validates the complete proposed catalogue, including component references.
    Empty or unknown PV output is never replaced with zero or a bus-power rating.
    """
    schema = load_schema()
    fields = schema["fields"]
    seen: set[str] = set()
    identities: set[tuple] = set()
    norad_ids: set[int] = set()
    cospar_ids: set[str] = set()
    equipment: set[tuple] = set()
    component_ids = {r.get("record_id") for r in records if r.get("entity_type") == "components"}
    for source_id, source in sources.items():
        if not isinstance(source_id, str) or not isinstance(source, dict):
            raise CatalogueError("Source registry must map IDs to objects")
        for key in ("url", "title", "publisher", "retrieved_at", "reuse_notes"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise CatalogueError(f"Source {source_id} missing {key}")
        parsed = urlparse(source["url"])
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise CatalogueError(f"Source {source_id} must have an HTTP(S) URL")
        _timestamp(source["retrieved_at"])
        if source.get("sha256") is not None and not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            raise CatalogueError(f"Invalid source hash: {source_id}")
    for row in records:
        missing = set(schema["required"]) - row.keys()
        unknown = row.keys() - fields.keys()
        if missing or unknown:
            raise CatalogueError(f"Missing {sorted(missing)} / unknown fields {sorted(unknown)}")
        for key, value in row.items():
            if value is None:
                if key in schema["required"]:
                    raise CatalogueError(f"Required field is null: {key}")
                continue
            kind = fields[key]["type"]
            valid = {
                "string": lambda value=value: isinstance(value, str) and bool(value.strip()),
                "number": lambda value=value: _number(value),
                "integer": lambda value=value: (
                    isinstance(value, int) and not isinstance(value, bool)
                ),
                "object": lambda value=value: isinstance(value, dict),
                "list_string": lambda value=value: (
                    isinstance(value, list)
                    and all(isinstance(v, str) and v for v in value)
                    and len(value) == len(set(value))
                ),
                "list_object": lambda value=value: (
                    isinstance(value, list) and all(isinstance(v, dict) for v in value)
                ),
            }[kind]()
            if not valid:
                raise CatalogueError(f"Invalid {key}: expected {kind}")
            if kind in {"number", "integer"} and key != "reference_temperature_c" and value < 0:
                raise CatalogueError(f"Negative {key}")
        entity = row["entity_type"]
        if entity not in schema["entity_types"]:
            raise CatalogueError(f"Unknown entity: {entity}")
        rid = record_id(entity, row["identity_key"])
        identity = (entity, row["identity_key"])
        if row["record_id"] != rid or rid in seen or identity in identities:
            raise CatalogueError("Duplicate or unstable record identity")
        seen.add(rid)
        identities.add(identity)
        created = _timestamp(row["created_at"])
        updated = _timestamp(row["updated_at"])
        verified = _timestamp(row["last_verified_at"])
        if not created <= updated <= verified:
            raise CatalogueError("Require created_at <= updated_at <= last_verified_at")
        if row["quality_status"] not in {"source_verified", "partial", "conflicting"}:
            raise CatalogueError("Invalid research quality_status")
        row_sources = set(row["sources"])
        if not row_sources or not row_sources <= sources.keys():
            raise CatalogueError("Unknown or empty source references")
        evidence = row["evidence_json"]
        if set(evidence) != row_sources:
            raise CatalogueError("Every record source requires evidence")
        for item in evidence.values():
            if not isinstance(item, dict) or not all(
                isinstance(item.get(k), str) and item[k].strip() for k in ("locator", "summary")
            ):
                raise CatalogueError("Evidence needs locator and summary")
        field_sources = row["field_sources_json"]
        for key, ids in field_sources.items():
            if (
                key not in fields
                or not isinstance(ids, list)
                or not ids
                or not set(ids) <= row_sources
            ):
                raise CatalogueError(f"Invalid field evidence: {key}")
        for key, value in row.items():
            if (
                key not in METADATA
                and value is not None
                and value != []
                and key not in field_sources
            ):
                raise CatalogueError(f"Missing field-level evidence: {key}")
        for key, registry in (("norad_id", norad_ids), ("cospar_id", cospar_ids)):
            value = row.get(key)
            if value is not None:
                if (
                    entity != "satellites"
                    or value in registry
                    or (key == "norad_id" and value <= 0)
                ):
                    raise CatalogueError(f"Duplicate or invalid {key}")
                registry.add(value)
        if row.get("cospar_id") and not re.fullmatch(r"\d{4}-\d{3}[A-Z]{1,3}", row["cospar_id"]):
            raise CatalogueError("Invalid COSPAR ID")
        if entity == "components":
            if not all(row.get(k) for k in ("manufacturer", "model", "component_type")):
                raise CatalogueError("Components require manufacturer, model and component_type")
            identity = (row["manufacturer"], row["model"], row.get("variant"))
            if identity in equipment:
                raise CatalogueError("Duplicate OEM model/configuration")
            equipment.add(identity)
            if row["component_type"] not in {
                "solar_cell",
                "cic",
                "solar_panel",
                "solar_array",
                "eps",
                "battery",
            }:
                raise CatalogueError("Invalid component category")
        if not set(row.get("component_ids") or []) <= component_ids:
            raise CatalogueError("Broken component reference")
        if row.get("cell_efficiency_pct") is not None and (
            not 0 < row["cell_efficiency_pct"] <= 100 or not row.get("efficiency_basis")
        ):
            raise CatalogueError("Efficiency must be in (0, 100] with a stated basis")
        for key in ("reference_distance_au", "reference_irradiance_w_m2"):
            if row.get(key) is not None and row[key] <= 0:
                raise CatalogueError(f"Nonpositive {key}")
        if row.get("status") and not row.get("status_as_of"):
            raise CatalogueError("Status needs a dated assertion")
        for key in ("launch_date", "status_as_of"):
            if row.get(key):
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[key]):
                    raise CatalogueError(f"Invalid ISO date: {key}")
                try:
                    datetime.fromisoformat(row[key])
                except ValueError as exc:
                    raise CatalogueError(f"Invalid ISO date: {key}") from exc
        if row.get("pv_power_w") is not None:
            for key in ("pv_power_qualifier", "power_basis", "power_conditions"):
                if not row.get(key):
                    raise CatalogueError(f"PV power requires {key}")
            _rating(
                {
                    "power_w": row["pv_power_w"],
                    "qualifier": row["pv_power_qualifier"],
                    "basis": row["power_basis"],
                    "conditions": row["power_conditions"],
                    "source_id": row["field_sources_json"]["pv_power_w"][0],
                },
                row_sources,
            )
            if entity == "components" and row["component_type"] in {"eps", "battery"}:
                raise CatalogueError("EPS throughput and battery power are not PV generation")
        for rating in row.get("power_ratings_json") or []:
            _rating(rating, row_sources)
        _json(row)  # Reject NaN/infinity even inside extensions and evidence.


def validate_catalogue(root: str | Path | None = None) -> dict:
    """Validate packaged or custom canonical data and return coverage statistics."""
    rows = load_records(root=root)
    validate_records(rows, load_sources(root))
    return coverage(rows)


def coverage(records: list[dict] | None = None) -> dict:
    """Counts and completeness; deliberately no sum of unlike PV power ratings."""
    rows = load_records() if records is None else records
    result = {}
    for entity in load_schema()["entity_types"]:
        subset = [row for row in rows if row["entity_type"] == entity]
        result[entity] = {
            "rows": len(subset),
            "pv_power_known": sum(row.get("pv_power_w") is not None for row in subset),
            "pv_power_documented": sum(
                row.get("pv_power_w") is not None or bool(row.get("power_ratings_json"))
                for row in subset
            ),
            "field_completeness": {
                field: sum(row.get(field) is not None for row in subset)
                for field in load_schema()["fields"]
            },
            "quality": dict(sorted(Counter(row["quality_status"] for row in subset).items())),
        }
    return result


def merge_records(
    existing: list[dict], incoming: list[dict], *, now: str
) -> tuple[list[dict], list[dict]]:
    """Fill unknowns only; any conflicting assertion leaves that record unchanged.

    Pure operation: validate the complete result before writing it. Ratings and
    nested extensions are atomic, so a different EOL value cannot silently replace
    a BOL assertion. Identical observations do not churn timestamps.
    """
    moment = _timestamp(now)
    merged = {row["record_id"]: copy.deepcopy(row) for row in existing}
    if len(merged) != len(existing) or len({r["record_id"] for r in incoming}) != len(incoming):
        raise CatalogueError("Duplicate record IDs in merge input")
    conflicts = []
    for new in incoming:
        rid = new["record_id"]
        if rid not in merged:
            merged[rid] = copy.deepcopy(new)
            continue
        old = merged[rid]
        if moment < _timestamp(old["last_verified_at"]) or moment < _timestamp(
            new["last_verified_at"]
        ):
            raise CatalogueError("Merge time predates the evidence")
        protected = set(old) | set(new)
        protected -= {
            "created_at",
            "updated_at",
            "last_verified_at",
            "sources",
            "field_sources_json",
            "evidence_json",
        }
        differences = [
            key
            for key in sorted(protected)
            if old.get(key) is not None and new.get(key) is not None and old[key] != new[key]
        ]
        evidence_differences = [
            key
            for key in set(old["evidence_json"]) & set(new["evidence_json"])
            if old["evidence_json"][key] != new["evidence_json"][key]
        ]
        if differences or evidence_differences:
            conflicts.append(
                {
                    "record_id": rid,
                    "fields": differences,
                    "evidence_sources": sorted(evidence_differences),
                    "incoming": new,
                }
            )
            continue
        before = _json(old)
        for key in protected:
            if old.get(key) is None and new.get(key) is not None:
                old[key] = copy.deepcopy(new[key])
        old["sources"] = sorted(set(old["sources"]) | set(new["sources"]))
        old["evidence_json"].update(copy.deepcopy(new["evidence_json"]))
        for key, ids in new["field_sources_json"].items():
            old["field_sources_json"][key] = sorted(
                set(old["field_sources_json"].get(key, [])) | set(ids)
            )
        if _json(old) != before:
            old["updated_at"] = now
            old["last_verified_at"] = now
    return sorted(merged.values(), key=lambda row: row["record_id"]), conflicts


def stage_omm(objects: list[dict], *, source_id: str, now: str) -> list[dict]:
    """Stage identities from supplied CelesTrak/CCSDS OMM; never infer PV capacity.

    Review against existing aliases/COSPAR IDs before admission. Exact source bytes,
    hash and provider terms belong in the caller's source registry. This function
    makes no HTTP requests and does not write canonical data.
    """
    _timestamp(now)
    if not isinstance(objects, list) or not all(isinstance(item, dict) for item in objects):
        raise CatalogueError("OMM input must be a JSON array of objects")
    if not isinstance(source_id, str) or not source_id.strip():
        raise CatalogueError("OMM staging requires a source ID")
    staged = []
    seen = set()
    for item in objects:
        raw = item.get("NORAD_CAT_ID")
        if isinstance(raw, bool) or not re.fullmatch(r"[1-9]\d*", str(raw)):
            raise CatalogueError("OMM requires a positive NORAD_CAT_ID")
        norad = int(str(raw))
        name = item.get("OBJECT_NAME")
        if norad in seen or not isinstance(name, str) or not name.strip():
            raise CatalogueError("Duplicate OMM identity or missing object name")
        seen.add(norad)
        key = f"norad:{norad}"
        values = {"name": name.strip(), "norad_id": norad}
        if item.get("OBJECT_ID"):
            values["cospar_id"] = item["OBJECT_ID"]
        staged.append(
            {
                "record_id": record_id("satellites", key),
                "identity_key": key,
                "entity_type": "satellites",
                **values,
                "created_at": now,
                "updated_at": now,
                "last_verified_at": now,
                "quality_status": "partial",
                "sources": [source_id],
                "field_sources_json": {k: [source_id] for k in values},
                "evidence_json": {
                    source_id: {
                        "locator": f"NORAD_CAT_ID={norad}",
                        "summary": "OMM identity only; no verified spacecraft PV rating in this source.",
                    }
                },
                "notes": "Identity candidate only. OMM does not establish PV capacity or operating status.",
            }
        )
    return staged


def build_snapshot(output: str | Path, root: str | Path | None = None) -> dict:
    """Build immutable typed Parquet tables, verified browser projections and manifest.

    Requires ``orbital-pv[catalogue]``. Same inputs and PyArrow version produce the
    same bytes; the manifest records PyArrow's version. Output must not exist.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError('Install "orbital-pv[catalogue]" to build Parquet snapshots') from exc
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Snapshot already exists: {output}")
    rows = load_records(root=root)
    sources = load_sources(root)
    validate_records(rows, sources)
    schema = load_schema()
    types = {
        "string": pa.string(),
        "number": pa.float64(),
        "integer": pa.int64(),
        "list_string": pa.list_(pa.string()),
        "object": pa.string(),
        "list_object": pa.string(),
    }
    arrow_schema = pa.schema(
        [(key, types[spec["type"]]) for key, spec in schema["fields"].items()]
        + [("source_urls", pa.list_(pa.string()))]
    )
    arrow_schema = arrow_schema.with_metadata(
        {b"orbitalpv_schema_version": schema["version"].encode()}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".satellite-snapshot-", dir=output.parent))
    try:
        manifest = {
            "schema_version": schema["version"],
            "pyarrow_version": pa.__version__,
            "canonical_sha256": hashlib.sha256(
                _json({"records": rows, "sources": sources, "schema": schema}).encode()
            ).hexdigest(),
            "coverage": coverage(rows),
            "files": {},
        }
        for name, data in (("schema.json", schema), ("sources.json", sources)):
            (stage / name).write_text(_json(data) + "\n", encoding="utf-8")
        shutil.copyfile(DATA_ROOT / "NOTICE.txt", stage / "NOTICE.txt")
        for entity in schema["entity_types"]:
            encoded = []
            for row in rows:
                if row["entity_type"] != entity:
                    continue
                item = {
                    key: (
                        _json(row[key])
                        if spec["type"] in {"object", "list_object"} and row.get(key) is not None
                        else row.get(key)
                    )
                    for key, spec in schema["fields"].items()
                }
                item["source_urls"] = [sources[s]["url"] for s in row["sources"]]
                encoded.append(item)
            table = pa.Table.from_pylist(encoded, schema=arrow_schema)
            pq.write_table(
                table, stage / f"{entity}.parquet", compression="zstd", use_dictionary=True
            )
            projection = pq.read_table(stage / f"{entity}.parquet").to_pylist()
            for row in projection:
                for key, spec in schema["fields"].items():
                    if spec["type"] in {"object", "list_object"} and row[key] is not None:
                        row[key] = json.loads(row[key])
            (stage / f"{entity}.json").write_text(_json(projection) + "\n", encoding="utf-8")
        for path in sorted(stage.iterdir()):
            manifest["files"][path.name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        (stage / "manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
        # A nonempty existing directory cannot be replaced; refuse even an empty one.
        if output.exists():
            raise FileExistsError(output)
        stage.rename(output)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)
