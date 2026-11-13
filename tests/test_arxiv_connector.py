from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from orbitalpv import ArxivConnector
from space_pv_connectors.arxiv import parse_arxiv_atom

# Synthetic protocol fixture, not a captured live response.
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/2511.19468v2</id><title> Example\n title </title>
<published>2025-11-22T00:28:08Z</published><updated>2026-06-17T09:31:06Z</updated>
<author><name>Example Author</name></author><category term="cs.DC"/>
</entry></feed>"""


def test_parse_and_pin_version():
    result = parse_arxiv_atom(ATOM, "2511.19468v2")
    assert result["title"] == "Example title"
    assert result["authors"] == ["Example Author"]
    assert result["categories"] == ["cs.DC"]
    with pytest.raises(ValueError, match="version"):
        parse_arxiv_atom(ATOM, "2511.19468v1")


@pytest.mark.parametrize("paper_id", ["2511.19468", "../file", "2511.19468v0", "2511.19468v2&x=1"])
def test_reject_unpinned_or_invalid_id(paper_id):
    with pytest.raises(ValueError):
        parse_arxiv_atom(ATOM, paper_id)


@pytest.mark.parametrize(
    "content",
    [
        b"<html>error</html>",
        b"<!DOCTYPE feed><feed/>",
        b"garbage",
        ATOM.replace(b"<author><name>Example Author</name></author>", b""),
        ATOM.replace(b"<title> Example\n title </title>", b""),
    ],
)
def test_reject_bad_feed(content):
    with pytest.raises(ValueError):
        parse_arxiv_atom(content, "2511.19468v2")


def test_live_protocol_cache_checksum_and_refresh(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.params["id_list"] == "2511.19468v2"
        return httpx.Response(200, content=ATOM)

    with ArxivConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(handle))
        cache = tmp_path / "paper.xml"
        first = connector.paper("2511.19468v2", cache_path=cache)
        second = connector.paper("2511.19468v2", cache_path=cache)
        assert first == second
        assert len(calls) == 1
        assert first.receipt.sha256 == hashlib.sha256(ATOM).hexdigest()
        assert cache.read_bytes() == ATOM
        with pytest.raises(ValueError, match="different request"):
            connector.paper("2511.19468v1", cache_path=cache)
        cache.write_bytes(ATOM + b" ")
        with pytest.raises(ValueError, match="checksum"):
            connector.paper("2511.19468v2", cache_path=cache)
        connector.paper("2511.19468v2", cache_path=cache, refresh=True)
        assert len(calls) == 2
        sidecar = cache.with_name(cache.name + ".provenance.json")
        provenance = json.loads(sidecar.read_text())
        assert provenance["source"] == "arXiv"
        sidecar.unlink()
        with pytest.raises(ValueError, match="sidecar"):
            connector.paper("2511.19468v2", cache_path=cache)


def test_failed_response_not_cached(tmp_path):
    with ArxivConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html/>"))
        )
        cache = tmp_path / "bad.xml"
        with pytest.raises(ValueError):
            connector.paper("2511.19468v2", cache_path=cache)
        assert not cache.exists()


def test_pdf_download_receipt(tmp_path):
    pdf = b"%PDF-1.4 synthetic-test-only"
    with ArxivConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, content=pdf, headers={"content-type": "application/pdf"}
                )
            )
        )
        target = tmp_path / "paper.pdf"
        receipt = connector.download_paper("2511.19468v2", target)
        assert target.read_bytes() == pdf
        assert receipt.sha256 == hashlib.sha256(pdf).hexdigest()
        assert receipt.url.endswith("/2511.19468v2")
