from space_pv_connectors.satnogs import SatnogsDbConnector


def test_satnogs_endpoints_are_public_https():
    assert SatnogsDbConnector.BASE_URL == "https://db.satnogs.org/api"
