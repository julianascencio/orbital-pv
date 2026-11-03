"""Research connector contracts: queries, provenance, failures and original bytes."""

import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import httpx
import pytest

import orbitalpv as opv
from space_pv_connectors.research_http import ResearchConnector


def mock_client(connector, handler):
    connector._client.close()
    connector._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return connector


def test_public_exports():
    import orbitalpv.data as data
    import space_pv_connectors as connectors

    for name in (
        "NtrsConnector",
        "DiscosConnector",
        "ZenodoConnector",
        "DataverseConnector",
        "HorizonsConnector",
        "PdsConnector",
        "PsaConnector",
        "DonkiConnector",
        "ResearchResponse",
    ):
        assert getattr(opv, name) is getattr(data, name) is getattr(connectors, name)


@pytest.mark.parametrize("sphinx_mode", [False, True])
def test_gallery_replays_all_seven_original_snapshots_offline(monkeypatch, sphinx_mode):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline research gallery attempted a network request")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    root = Path(__file__).resolve().parents[1]
    example = root / "examples/real_data/plot_research_connectors.py"
    result: dict[str, Any]
    if sphinx_mode:
        monkeypatch.chdir(example.parent)
        result = {"__name__": "__main__"}
        exec(compile(example.read_text(), str(example), "exec"), result)
    else:
        result = runpy.run_path(str(example))
    assert len(result["events"]) == 28
    assert len(result["distance_au"]) == 4
    assert (result["distance_au"] > 4).all()
    assert result["zenodo"].data["id"] == 15108715
    import matplotlib.pyplot as plt

    plt.close(result["fig"])


def test_ntrs_pagination_and_provenance(tmp_path):
    payload = {
        "stats": {"total": 57},
        "results": [{"id": 123, "title": "Solar array", "downloads": []}],
    }
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["page.from"] == "25"
        assert request.url.params["page.size"] == "25"
        assert request.url.params["q"] == '"solar array"'
        return httpx.Response(200, json=payload)

    path = tmp_path / "query.json"
    with mock_client(opv.NtrsConnector(), handler) as api:
        result = api.search('"solar array"', offset=25, cache_path=path)
        cached = api.search('"solar array"', offset=25, cache_path=path)
        assert len(calls) == 1
        assert cached.data == result.data == payload
        assert cached.receipt == result.receipt
        assert result.receipt.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert result.data["stats"]["total"] > len(result.data["results"])
        with pytest.raises(ValueError, match="different request"):
            api.search("different", offset=25, cache_path=path)
        api.search('"solar array"', offset=25, cache_path=path, refresh=True)
        assert len(calls) == 2
        path.write_text("{}")
        with pytest.raises(ValueError, match="checksum"):
            api.search('"solar array"', offset=25, cache_path=path)


def test_cache_without_sidecar_fails(tmp_path):
    path = tmp_path / "missing.json"
    path.write_text("{}")
    with opv.NtrsConnector() as api, pytest.raises(ValueError, match="sidecar"):
        api.search("array", cache_path=path)


@pytest.mark.parametrize(
    "payload", [{"error": "invalid"}, {"errors": ["invalid"]}, {"status": "ERROR"}, {}]
)
def test_failed_json_not_cached(tmp_path, payload):
    with mock_client(opv.NtrsConnector(), lambda r: httpx.Response(200, json=payload)) as api:
        path = tmp_path / "failed.json"
        with pytest.raises(ValueError):
            api.search("array", cache_path=path)
        assert not path.exists()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 503])
def test_http_errors_surface_without_retry_or_empty_results(status, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "upstream"}, headers={"Retry-After": "60"})

    with mock_client(opv.ZenodoConnector(), handler) as api:
        with pytest.raises(httpx.HTTPStatusError) as error:
            api.search("solar", cache_path=tmp_path / "failed.json")
        assert error.value.response.status_code == status
        assert error.value.response.headers["Retry-After"] == "60"
        assert len(calls) == 1
        assert not (tmp_path / "failed.json").exists()


def test_html_login_not_cached(tmp_path):
    with mock_client(
        opv.NtrsConnector(), lambda r: httpx.Response(200, text="<html>Login</html>")
    ) as api:
        with pytest.raises(ValueError, match="valid JSON"):
            api.search("array", cache_path=tmp_path / "login.json")
        assert not (tmp_path / "login.json").exists()


def test_discos_auth_identifiers_and_no_token_in_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-secret-token"
        assert request.headers["DiscosWeb-Api-Version"] == "2"
        if request.url.path.endswith("/objects/123"):
            return httpx.Response(200, json={"data": {"id": "123", "attributes": {"satno": 25544}}})
        assert request.url.params["filter"] == "eq(satno,25544)"
        assert request.url.params["page[number]"] == "1"
        return httpx.Response(200, json={"data": [], "links": {"next": None}})

    with mock_client(opv.DiscosConnector(token="test-secret-token"), handler) as api:
        assert api.by_norad(25544, cache_path=tmp_path / "discos.json").data["data"] == []
        assert api.object(123).data["data"]["id"] == "123"
    assert len(calls) == 2
    assert "test-secret-token" not in (tmp_path / "discos.json.provenance.json").read_text()


@pytest.mark.parametrize("token", ["", "  ", None])
def test_discos_requires_explicit_token(token):
    with pytest.raises(ValueError):
        opv.DiscosConnector(token=token)


def test_zenodo_queries_and_verified_download(tmp_path):
    content = b"voltage,current\n3.1,0.2\n"
    checksum = hashlib.md5(content).hexdigest()

    def handler(request):
        assert "authorization" not in request.headers
        if request.url.path == "/api/records":
            assert request.url.params["page"] == "2"
            return httpx.Response(200, json={"hits": {"total": 99, "hits": []}})
        if request.url.path == "/api/records/42":
            return httpx.Response(
                200,
                json={
                    "doi": "10.5281/zenodo.42",
                    "metadata": {"license": {"id": "cc-by-4.0"}},
                    "files": [
                        {
                            "key": "power.csv",
                            "checksum": f"md5:{checksum}",
                            "links": {
                                "self": "https://zenodo.org/api/records/42/files/power.csv/content"
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, content=content)

    with mock_client(opv.ZenodoConnector(), handler) as api:
        assert api.search("solar", page=2).data["hits"]["total"] == 99
        receipt = api.download_file(42, "power.csv", tmp_path / "power.csv")
        assert receipt.sha256 == hashlib.sha256(content).hexdigest()
        assert (tmp_path / "power.csv").read_bytes() == content
        meta = json.loads((tmp_path / "power.csv.provenance.json").read_text())
        assert meta["context"]["license"]["id"] == "cc-by-4.0"
        with pytest.raises(LookupError):
            api.download_file(42, "missing", tmp_path / "missing")


def test_ntrs_download_preserves_rights(tmp_path):
    def handler(request):
        if request.url.path.endswith("/123"):
            return httpx.Response(
                200,
                json={
                    "title": "Report",
                    "copyright": {"belongsToAuthors": True},
                    "distribution": "PUBLIC",
                    "downloads": [
                        {
                            "name": "report.pdf",
                            "links": {"original": "/api/citations/123/downloads/report.pdf"},
                        }
                    ],
                },
            )
        assert request.url.path == "/api/citations/123/downloads/report.pdf"
        return httpx.Response(
            200, content=b"%PDF-1.7 test", headers={"Content-Type": "application/pdf"}
        )

    with mock_client(opv.NtrsConnector(), handler) as api:
        api.download_document(123, "report.pdf", tmp_path / "report.pdf")
    meta = json.loads((tmp_path / "report.pdf.provenance.json").read_text())
    assert meta["context"]["copyright"]["belongsToAuthors"] is True


@pytest.mark.parametrize("failure", ["checksum", "size", "html"])
def test_download_failures_preserve_existing_file(tmp_path, failure):
    path = tmp_path / "file"
    path.write_bytes(b"previous valid data")
    headers = {"Content-Type": "text/html"} if failure == "html" else {}
    with (
        mock_client(
            ResearchConnector(), lambda r: httpx.Response(200, content=b"abc", headers=headers)
        ) as api,
        pytest.raises(ValueError),
    ):
        api._download(
            "https://example.org/file",
            path,
            max_bytes=2 if failure == "size" else 10,
            checksum="sha256:" + "0" * 64 if failure == "checksum" else None,
        )
    assert path.read_bytes() == b"previous valid data"
    assert not (tmp_path / "file.provenance.json").exists()


def test_dataverse_published_version_original_bytes(tmp_path):
    content = b"original table bytes"

    def handler(request):
        if request.url.path.endswith("/search"):
            assert request.url.params["type"] == "dataset"
            assert request.url.params["start"] == "50"
            return httpx.Response(200, json={"status": "OK", "data": {"items": []}})
        if "/versions/" in request.url.path:
            assert request.url.path.endswith("/versions/1.0")
            assert request.url.params["persistentId"] == "doi:10.1/data"
            return httpx.Response(
                200,
                json={
                    "status": "OK",
                    "data": {
                        "versionNumber": 1,
                        "versionMinorNumber": 0,
                        "license": {"name": "CC BY 4.0"},
                        "files": [
                            {
                                "restricted": False,
                                "dataFile": {
                                    "id": 9,
                                    "filename": "table.tab",
                                    "checksum": {
                                        "type": "SHA-256",
                                        "value": hashlib.sha256(content).hexdigest(),
                                    },
                                },
                            }
                        ],
                    },
                },
            )
        assert request.url.path == "/api/access/datafile/9"
        assert request.url.params["format"] == "original"
        return httpx.Response(200, content=content)

    with mock_client(opv.DataverseConnector(), handler) as api:
        api.search("power", start=50)
        api.download_file("doi:10.1/data", "table.tab", tmp_path / "original.tab", version="1.0")
    assert (tmp_path / "original.tab").read_bytes() == content


def test_dataverse_restricted_file_never_downloaded(tmp_path):
    def handler(request):
        assert "/versions/" in request.url.path
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "data": {
                    "files": [
                        {"restricted": True, "dataFile": {"filename": "secret.csv"}},
                    ]
                },
            },
        )

    with mock_client(opv.DataverseConnector(), handler) as api, pytest.raises(PermissionError):
        api.download_file("doi:10.1/data", "secret.csv", tmp_path / "secret")


def test_horizons_explicit_geometry_and_no_silent_unit_conversion():
    def handler(request):
        p = request.url.params
        assert p["COMMAND"] == "'-61'"
        assert p["CENTER"] == "'500@10'"
        assert p["TIME_TYPE"] == "TDB"
        assert p["OUT_UNITS"] == "AU-D"
        assert p["REF_SYSTEM"] == "ICRF"
        assert p["REF_PLANE"] == "FRAME"
        assert p["VEC_CORR"] == "NONE"
        return httpx.Response(
            200,
            json={"result": "headers\n$$SOE\nraw vectors\n$$EOE", "signature": {"version": "1.3"}},
        )

    with mock_client(opv.HorizonsConnector(), handler) as api:
        result = api.vectors("-61", start="2024-01-01", stop="2024-01-02")
        assert "raw vectors" in result.data["result"]


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "No ephemeris for target"},
        {"result": "Multiple targets match", "signature": {}},
    ],
)
def test_horizons_semantic_failure(payload):
    with (
        mock_client(opv.HorizonsConnector(), lambda r: httpx.Response(200, json=payload)) as api,
        pytest.raises(ValueError),
    ):
        api.vectors("Juno", start="2024-01-01", stop="2024-01-02")


def test_pds_query_and_cursor_are_preserved():
    def handler(request):
        assert request.url.params["q"] == '(product_class eq "Product_Bundle")'
        assert request.url.params["sort"] == "lid"
        assert request.url.params["search-after"] == "urn:nasa:pds:example"
        return httpx.Response(200, json={"data": [], "summary": {"hits": 0}})

    with mock_client(opv.PdsConnector(), handler) as api:
        assert (
            api.search(
                '(product_class eq "Product_Bundle")',
                sort="lid",
                search_after="urn:nasa:pds:example",
            ).data["data"]
            == []
        )
        with pytest.raises(ValueError, match="sort"):
            api.search("query", search_after="cursor")


def test_pds_versioned_product_identifier():
    def handler(request):
        assert request.url.path.endswith("/products/urn:nasa:pds:test::1.0")
        return httpx.Response(200, json={"id": "urn:nasa:pds:test::1.0", "properties": {}})

    with mock_client(opv.PdsConnector(), handler) as api:
        assert api.product("urn:nasa:pds:test::1.0").data["id"].endswith("::1.0")


def test_psa_preserves_column_units_and_limits():
    payload = {"metadata": [{"name": "time_min", "unit": "d"}], "data": [[2451545.0]]}

    def handler(request):
        p = request.url.params
        assert p["LANG"] == "ADQL" and p["FORMAT"] == "json" and p["MAXREC"] == "5"
        assert p["QUERY"] == "SELECT TOP 5 time_min FROM psa.epn_core"
        return httpx.Response(200, json=payload)

    with mock_client(opv.PsaConnector(), handler) as api:
        assert api.query("SELECT TOP 5 time_min FROM psa.epn_core", max_records=5).data == payload


def test_psa_rejects_invalid_rows():
    with (
        mock_client(
            opv.PsaConnector(),
            lambda r: httpx.Response(
                200,
                json={
                    "metadata": [{"name": "time_min"}],
                    "data": [[1, 2]],
                },
            ),
        ) as api,
        pytest.raises(ValueError, match="row width"),
    ):
        api.query("SELECT * FROM psa.epn_core")


@pytest.mark.parametrize("payload", [None, [], [{"flrID": "event-1", "instruments": []}]])
def test_donki_current_host_and_empty_window(payload):
    def handler(request):
        assert request.url.host == "ccmc.gsfc.nasa.gov"
        assert request.url.path == "/DONKI/WS/get/FLR"
        assert request.url.params["startDate"] == "2024-05-10"
        assert request.url.params["endDate"] == "2024-05-10"
        assert "api_key" not in request.url.params
        return httpx.Response(
            200, content=json.dumps(payload), headers={"Content-Type": "application/json"}
        )

    with mock_client(opv.DonkiConnector(), handler) as api:
        assert api.events("FLR", start="2024-05-10", stop="2024-05-10").data == payload


@pytest.mark.parametrize(
    "call",
    [
        lambda: opv.NtrsConnector().search("", page_size=2),
        lambda: opv.NtrsConnector().search("solar", page_size=True),
        lambda: opv.NtrsConnector().search("solar", offset=-1),
        lambda: opv.ZenodoConnector().search("solar", page_size=26),
        lambda: opv.ZenodoConnector().record("../42"),
        lambda: opv.DataverseConnector(base_url="http://example.org"),
        lambda: opv.DataverseConnector().dataset("doi:10.1/data", version=":draft"),
        lambda: opv.HorizonsConnector().vectors("-61", start="2024-02-30", stop="2024-03-01"),
        lambda: opv.HorizonsConnector().vectors(
            "-61", start="2024-01-01", stop="2024-01-02", step="0 d"
        ),
        lambda: opv.HorizonsConnector().vectors("'-61'", start="2024-01-01", stop="2024-01-02"),
        lambda: opv.PsaConnector().query("DELETE FROM psa.epn_core"),
        lambda: opv.DonkiConnector().events("bad", start="2024-01-01", stop="2024-01-02"),
        lambda: opv.DonkiConnector().events("FLR", start="2024-01-02", stop="2024-01-01"),
    ],
)
def test_invalid_requests_fail_before_network(call, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input made a network request")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    with pytest.raises(ValueError):
        call()
