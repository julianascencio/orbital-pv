import pytest

from space_pv_connectors.celestrak import CelesTrakConnector
from space_pv_connectors.naif import NaifKernelConnector


def test_celestrak_requires_one_query():
    with CelesTrakConnector() as connector:
        with pytest.raises(ValueError):
            connector.fetch_gp()
        with pytest.raises(ValueError):
            connector.fetch_gp(catnr=25544, group="stations")


def test_naif_restricts_host(tmp_path):
    with NaifKernelConnector() as connector, pytest.raises(ValueError):
        connector.download("https://example.com/kernel.bsp", tmp_path / "kernel.bsp")
