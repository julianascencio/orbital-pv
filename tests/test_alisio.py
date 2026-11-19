"""ALISIO-1 source identity, download receipts and offline gallery contracts."""

import json
import runpy
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import numpy as np
import pytest

import orbitalpv as opv

ROOT = Path(__file__).resolve().parents[1]


def test_original_download_matches_offline_png_and_records_source(tmp_path, monkeypatch):
    scene = opv.AlisioConnector.scenes["la-palma"]
    original = opv.AlisioConnector.bundled_image("la-palma")

    def respond(request):
        assert request.url.host == "cloud.iac.es"
        assert request.url.params["files"] == "la_palma.png"
        assert request.url.params["path"] == "/Primeras imágenes ALISIO-1 (Feb. 2024)/Imágenes"
        return httpx.Response(200, content=original, headers={"Content-Type": "image/png"})

    dest = tmp_path / "island.png"
    with (
        opv.AlisioConnector() as iac,
        httpx.Client(transport=httpx.MockTransport(respond)) as http,
        monkeypatch.context() as patch,
    ):
        patch.setattr(iac, "_client", http)
        receipt = iac.download("la-palma", dest)
    assert dest.read_bytes() == original
    assert receipt.sha256 == scene.sha256
    sidecar = json.loads((tmp_path / "island.png.provenance.json").read_text())
    assert sidecar["request_url"] == scene.url
    assert sidecar["context"]["credit"] == iac.CREDIT
    assert sidecar["context"]["usage_terms"] == iac.USAGE_TERMS


def test_changed_upstream_preserves_existing_file(tmp_path, monkeypatch):
    dest = tmp_path / "image.jpg"
    dest.write_bytes(b"existing")
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"changed"))
    with (
        opv.AlisioConnector() as iac,
        httpx.Client(transport=transport) as http,
        monkeypatch.context() as patch,
    ):
        patch.setattr(iac, "_client", http)
        with pytest.raises(ValueError, match="checksum"):
            iac.download("donana", dest)
    assert dest.read_bytes() == b"existing"
    assert not (tmp_path / "image.jpg.provenance.json").exists()
    with pytest.raises(ValueError, match="download"):
        opv.AlisioConnector.bundled_image("donana")


def test_gallery_runs_offline_and_budget_units(monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("An offline ALISIO-1 example attempted a network request")

    monkeypatch.setattr(httpx.Client, "send", no_network)
    images = runpy.run_path(str(ROOT / "examples/ground_imagery/plot_alisio_canary_islands.py"))
    assert [ax.images[0].get_array().shape[:2] for ax in images["axes"]] == [
        (1059, 837),
        (593, 691),
    ]
    plt.close(images["fig"])
    budget = runpy.run_path(str(ROOT / "examples/space_business/plot_alisio_imaging_energy.py"))
    ten_minutes = np.where(budget["active_minutes"] == 10)[0].item()
    assert budget["camera_energy_wh"][ten_minutes] == pytest.approx(5.5 / 6)
    assert budget["array_energy_wh"][ten_minutes] == pytest.approx(5.5 / 6 / 0.8)
    assert budget["mean_array_power_w"][ten_minutes] == pytest.approx(5.5 / 6 / 0.8 / 0.5)
    plt.close(budget["fig"])
