from pathlib import Path


def test_application_platform_scaffold_exists() -> None:
    root = Path(__file__).parents[1]
    expected = [
        root / "apps/space-pv-api/pyproject.toml",
        root / "apps/space-pv-web/package.json",
        root / "packages/space-pv-storage/pyproject.toml",
        root / "packages/space-pv-orchestration/pyproject.toml",
        root / "compose.yaml",
    ]
    assert all(path.exists() for path in expected)
