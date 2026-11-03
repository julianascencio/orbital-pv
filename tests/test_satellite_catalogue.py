"""Catalogue identity, evidence, scientific semantics and distribution contracts."""

import copy
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from orbitalpv.catalogue import (
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


@pytest.fixture
def catalogue():
    return load_records(), load_sources()


def test_packaged_catalogue_and_evidenced_links(catalogue):
    rows, sources = catalogue
    stats = validate_catalogue()
    assert stats["satellites"]["rows"] >= 25
    assert stats["components"]["rows"] >= 18
    assert len(sources) >= 35
    assert any(row.get("component_ids") for row in rows)
    assert any(row["quality_status"] == "conflicting" for row in rows)
    assert any(row.get("power_ratings_json") for row in rows)
    assert not any("total_power" in key for key in stats)


def test_unknown_and_ambiguous_power_do_not_become_pv():
    rows = {row["name"]: row for row in load_records("satellites")}
    assert rows["GSAT-11"]["reported_spacecraft_power_w"] == 13600
    assert rows["GSAT-11"].get("pv_power_w") is None
    assert rows["Solar Orbiter"].get("pv_power_w") is None
    assert rows["SPACE HAUC"].get("pv_power_w") is None
    assert rows["AstroSat"].get("pv_power_w") is None
    assert len(rows["AstroSat"]["power_ratings_json"]) == 2


def test_reference_distance_and_efficiency_conditions():
    satellites = {row["name"]: row for row in load_records("satellites")}
    rosetta = satellites["Rosetta orbiter"]
    assert rosetta["reference_distance_au"] == 3.4
    assert rosetta["power_ratings_json"][0]["distance_au"] == 5.25
    cells = {row["name"]: row for row in load_records("components")}
    assert cells["Spectrolab XTE-LILT"]["cell_efficiency_pct"] == 31.6
    assert cells["Spectrolab XTE-LILT"]["reference_temperature_c"] == 28
    assert cells["AZUR SPACE 3G30C-Advanced"]["cell_efficiency_pct"] == 29.5
    assert cells["AZUR SPACE 3G30A-Advanced"]["cell_efficiency_pct"] == 29.2


@pytest.mark.parametrize(
    "change",
    [
        {"pv_power_w": -1},
        {"pv_power_w": True},
        {"pv_power_w": float("nan")},
        {"pv_power_w": float("inf")},
        {"pv_power_qualifier": "nominal"},
        {"power_basis": "AC"},
        {"power_conditions": ""},
        {"power_conditions": None},
        {"component_ids": ["missing"]},
        {"reference_distance_au": 0},
        {"norad_id": False},
        {"norad_id": 0},
        {"unknown_column": 1},
        {"status": "operational"},
        {"launch_date": "2026-02-30"},
        {"updated_at": "2000-01-01T00:00:00Z"},
        {"extensions_json": {"x": float("inf")}},
    ],
)
def test_reject_bad_ratings_and_metadata(catalogue, change):
    rows, sources = catalogue
    row = next(r for r in rows if r.get("pv_power_w") is not None)
    row.update(change)
    with pytest.raises((CatalogueError, ValueError)):
        validate_records(rows, sources)


def test_no_unsourced_fields_or_links(catalogue):
    rows, sources = catalogue
    row = next(r for r in rows if r.get("pv_power_w") is not None)
    del row["field_sources_json"]["pv_power_w"]
    with pytest.raises(CatalogueError, match="Missing field-level evidence"):
        validate_records(rows, sources)


def test_source_registry_and_evidence(catalogue):
    rows, sources = catalogue
    source = rows[0]["sources"][0]
    sources[source]["url"] = "javascript:alert(1)"
    with pytest.raises(CatalogueError, match="HTTP"):
        validate_records(rows, sources)


def test_duplicate_identity_and_norad_rejected(catalogue):
    rows, sources = catalogue
    with pytest.raises(CatalogueError, match="Duplicate"):
        validate_records([*rows, rows[0]], sources)
    sats = [row for row in rows if row["entity_type"] == "satellites"]
    for row in sats[:2]:
        row["norad_id"] = 123456
        row["field_sources_json"]["norad_id"] = row["sources"]
    with pytest.raises(CatalogueError, match="norad_id"):
        validate_records(rows, sources)


def test_case_sensitive_oem_identity():
    assert record_id("components", "Maker|Xb") != record_id("components", "Maker|XB")
    assert record_id("satellites", "norad:123456") == record_id("satellites", "norad:123456")


def test_conservative_merge_conflict_and_idempotence(catalogue):
    rows, sources = catalogue
    target = next(r for r in rows if r.get("pv_power_w") is not None)
    incoming = copy.deepcopy(target)
    now = "2026-11-03T00:00:00Z"
    merged, conflicts = merge_records(rows, [incoming], now=now)
    assert not conflicts
    assert merged == rows
    incoming["pv_power_w"] += 1
    merged, conflicts = merge_records(rows, [incoming], now=now)
    assert conflicts[0]["fields"] == ["pv_power_w"]
    assert merged == rows
    validate_records(merged, sources)


def test_merge_fills_unknown_preserves_dates_and_provenance(catalogue):
    rows, sources = catalogue
    row = next(r for r in rows if r["entity_type"] == "satellites" and r.get("norad_id") is None)
    incoming = copy.deepcopy(row)
    incoming["norad_id"] = 123456
    incoming["field_sources_json"]["norad_id"] = row["sources"]
    incoming["created_at"] = "2026-11-03T00:00:00Z"
    merged, conflicts = merge_records(rows, [incoming], now="2026-11-03T00:00:00Z")
    assert not conflicts
    changed = next(r for r in merged if r["record_id"] == row["record_id"])
    assert changed["created_at"] == row["created_at"]
    assert changed["updated_at"] == "2026-11-03T00:00:00Z"
    validate_records(merged, sources)
    assert row.get("norad_id") is None  # Caller data untouched.


def test_omm_is_staging_only_six_digit_ids_and_no_pv():
    omm = [
        {
            "NORAD_CAT_ID": 123456,
            "OBJECT_NAME": "Example",
            "OBJECT_ID": "2026-001A",
            "MEAN_MOTION": 15.2,
        }
    ]
    rows = stage_omm(omm, source_id="fixture", now="2026-11-02T00:00:00Z")
    assert rows[0]["norad_id"] == 123456
    assert rows[0].get("pv_power_w") is None
    assert rows[0].get("status") is None
    assert rows[0]["record_id"] == record_id("satellites", "norad:123456")
    with pytest.raises(CatalogueError, match="Duplicate"):
        stage_omm(omm * 2, source_id="fixture", now="2026-11-02T00:00:00Z")
    with pytest.raises(CatalogueError):
        stage_omm(
            [{"NORAD_CAT_ID": 1.5, "OBJECT_NAME": "Invalid"}],
            source_id="fixture",
            now="2026-11-02T00:00:00Z",
        )


def test_snapshot_roundtrip_checksums_and_repeatability(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    manifest = build_snapshot(first)
    assert manifest == build_snapshot(second)
    for name, metadata in manifest["files"].items():
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == metadata["sha256"]
    for entity in ("satellites", "components"):
        table = pq.read_table(first / f"{entity}.parquet")
        assert table.schema.field("pv_power_w").type == pa.float64()
        assert table.schema.field("norad_id").type == pa.int64()
        assert table.schema.field("sources").type == pa.list_(pa.string())
        assert table.schema.field("field_sources_json").type == pa.string()
        browser = json.loads((first / f"{entity}.json").read_text())
        assert len(browser) == len(load_records(entity))
        for canonical, exported in zip(load_records(entity), browser, strict=True):
            for key, value in canonical.items():
                assert exported[key] == value
        assert table.column_names == [*load_schema()["fields"], "source_urls"]
    with pytest.raises(FileExistsError):
        build_snapshot(first)


def test_wrong_shard_rejected(tmp_path):
    row = load_records("satellites")[0]
    folder = tmp_path / "records" / "satellites"
    folder.mkdir(parents=True)
    (folder / "wrong.jsonl").write_text(json.dumps(row))
    with pytest.raises(CatalogueError, match="shard"):
        load_records(root=tmp_path)


def test_package_data_is_under_installable_module():
    import orbitalpv.catalogue.core as core

    assert Path(core.__file__).with_name("data").joinpath("sources.json").exists()
    assert coverage()["components"]["rows"] == len(load_records("components"))
