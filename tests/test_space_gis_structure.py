from pathlib import Path


def test_space_gis_scaffold_exists() -> None:
    root = Path(__file__).parents[1]
    expected = [root / "infra/postgres/init/001_space_gis.sql", root / "docs/space_gis_and_visualization.md", root / "packages/space-pv-storage/src/space_pv_storage/map_store.py", root / "apps/space-pv-web/src/components/SpaceGlobe.tsx"]
    assert all(path.exists() for path in expected)
