from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOTS = [ROOT / "examples", ROOT / "labs"]


def test_examples_use_public_orbitalpv_api() -> None:
    python_files = sorted(path for root in EXAMPLE_ROOTS for path in root.rglob("*.py"))
    assert python_files

    violations: list[str] = []
    for path in python_files:
        text = path.read_text(encoding="utf-8")
        if "space_pv_" in text:
            violations.append(f"{path.relative_to(ROOT)} imports an internal space_pv_* module")
        if "import orbitalpv" not in text and "from orbitalpv" not in text:
            violations.append(f"{path.relative_to(ROOT)} does not import orbitalpv")

    assert not violations, "\n".join(violations)
