"""Free spacecraft metadata, technical literature, archives and geometry APIs.

These connectors return provider facts with provenance. They do not infer PV
ratings, parse technical papers into accepted catalogue records, or turn space
weather events into spacecraft radiation doses. Searches return one bounded
page; retain provider totals/links and request subsequent pages explicitly.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote

import httpx

from .http_base import DownloadReceipt
from .research_http import (
    ResearchConnector,
    ResearchResponse,
    bounded_int,
    require_fields,
    required_text,
)


def _id(value: int | str) -> str:
    text = str(value)
    if not text.isascii() or not text.isdigit() or int(text) <= 0:
        raise ValueError("Record ID must be a positive integer")
    return text


def _dates(start: str, stop: str) -> None:
    if not all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in (start, stop)):
        raise ValueError("Dates must have YYYY-MM-DD format")
    if date.fromisoformat(stop) < date.fromisoformat(start):
        raise ValueError("end date must not precede start date")


class NtrsConnector(ResearchConnector):
    """NASA Technical Reports Server: public metadata and available documents.

    No account is needed. A search hit can be metadata-only. Preserve each
    record's copyright/distribution fields; public access is not a blanket
    license to redistribute every paper. Design goals in papers are not flight
    performance measurements.
    """

    BASE_URL = "https://ntrs.nasa.gov/api"
    SOURCE = "NASA NTRS"
    DOCUMENTATION = "https://ntrs.nasa.gov/api/openapi/"

    def search(
        self,
        query: str,
        *,
        offset: int = 0,
        page_size: int = 25,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Search one page; ``offset`` is the zero-based record offset."""
        return self._json(
            f"{self.BASE_URL}/citations/search",
            params={
                "q": required_text(query, "query"),
                "page.from": bounded_int(offset, "offset", 0, 10_000_000),
                "page.size": bounded_int(page_size, "page_size", 1, 100),
            },
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, results=list, stats=dict),
        )

    def citation(
        self,
        citation_id: int | str,
        *,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Get metadata, original download links and access/copyright details."""
        return self._json(
            f"{self.BASE_URL}/citations/{_id(citation_id)}",
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, title=str, downloads=list),
        )

    def download_document(
        self,
        citation_id: int | str,
        filename: str,
        destination: str | Path,
        *,
        max_bytes: int = 100_000_000,
    ) -> DownloadReceipt:
        """Download an explicitly selected, publicly available original file."""
        record = self.citation(citation_id).data
        matches = [
            d for d in record["downloads"] if d.get("name") == filename and not d.get("draft")
        ]
        if len(matches) != 1:
            raise LookupError("No unique public original document with that filename")
        path = matches[0].get("links", {}).get("original", "")
        prefix = f"/api/citations/{_id(citation_id)}/downloads/"
        if not isinstance(path, str) or not path.startswith(prefix):
            raise ValueError("NTRS returned an unexpected download location")
        return self._download(
            f"https://ntrs.nasa.gov{path}",
            destination,
            max_bytes=max_bytes,
            context={
                "citation_id": _id(citation_id),
                "filename": filename,
                "copyright": record.get("copyright"),
                "distribution": record.get("distribution"),
            },
        )


class DiscosConnector(ResearchConnector):
    """ESA DISCOS v2 metadata; free registration and an explicit token required.

    DISCOS IDs and NORAD catalog numbers are different identifiers. This API
    supplies object/launch metadata, not ephemerides or universal PV ratings.
    """

    BASE_URL = "https://discosweb.esoc.esa.int/api"
    SOURCE = "ESA DISCOSweb v2"
    DOCUMENTATION = "https://discosweb.esoc.esa.int/apidocs/v2"

    def __init__(self, *, token: str, timeout_s: float = 30.0):
        required_text(token, "token")
        super().__init__(timeout_s=timeout_s)
        self._headers = {"Authorization": f"Bearer {token}", "DiscosWeb-Api-Version": "2"}

    def objects(
        self,
        *,
        filter_expression: str | None = None,
        page: int = 1,
        page_size: int = 100,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Get one page of objects using the provider's filter syntax."""
        params: dict[str, Any] = {
            "page[number]": bounded_int(page, "page", 1, 10_000_000),
            "page[size]": bounded_int(page_size, "page_size", 1, 100),
        }
        if filter_expression is not None:
            params["filter"] = required_text(filter_expression, "filter_expression")
        return self._json(
            f"{self.BASE_URL}/objects",
            params=params,
            headers=self._headers,
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, data=list),
        )

    def object(
        self,
        discos_id: int | str,
        *,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Retrieve one object by its DISCOS internal ID."""
        return self._json(
            f"{self.BASE_URL}/objects/{_id(discos_id)}",
            headers=self._headers,
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, data=dict),
        )

    def by_norad(
        self,
        norad_id: int | str,
        *,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Search the NORAD ``satno`` field; preserve an empty or ambiguous result."""
        return self.objects(
            filter_expression=f"eq(satno,{_id(norad_id)})",
            cache_path=cache_path,
            refresh=refresh,
        )


class ZenodoConnector(ResearchConnector):
    """Discover published research datasets and download open files anonymously.

    Restricted files remain restricted. Each record supplies its own license;
    no deposit, publication or authenticated write endpoints are used.
    """

    BASE_URL = "https://zenodo.org/api"
    SOURCE = "Zenodo"
    DOCUMENTATION = "https://developers.zenodo.org/"

    def search(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int = 25,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Search one page using Zenodo query syntax (anonymous maximum: 25)."""
        return self._json(
            f"{self.BASE_URL}/records",
            params={
                "q": required_text(query, "query"),
                "page": bounded_int(page, "page", 1, 10_000_000),
                "size": bounded_int(page_size, "page_size", 1, 25),
            },
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, hits=dict),
        )

    def record(
        self,
        record_id: int | str,
        *,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Read a specific record/version, including DOI, license and file checksums."""
        return self._json(
            f"{self.BASE_URL}/records/{_id(record_id)}",
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, metadata=dict),
        )

    def download_file(
        self,
        record_id: int | str,
        filename: str,
        destination: str | Path,
        *,
        max_bytes: int = 100_000_000,
    ) -> DownloadReceipt:
        """Select a public file by exact name and verify its provider checksum."""
        record = self.record(record_id).data
        matches = [f for f in record.get("files", []) if f.get("key") == filename]
        if len(matches) != 1:
            raise LookupError("No unique public file with that filename")
        file = matches[0]
        url = file.get("links", {}).get("self", "")
        if httpx.URL(url).host != "zenodo.org" or not file.get("checksum"):
            raise ValueError("Zenodo file has no trusted download URL/checksum")
        return self._download(
            url,
            destination,
            checksum=file["checksum"],
            max_bytes=max_bytes,
            context={
                "record_id": _id(record_id),
                "doi": record.get("doi"),
                "license": record["metadata"].get("license"),
                "filename": filename,
            },
        )


class DataverseConnector(ResearchConnector):
    """Public Dataverse search and versioned dataset access; defaults to DaRUS.

    Another public installation can be selected with ``base_url``. Dataset and
    file licenses are provider-specific. Private/restricted data are not fetched.
    """

    SOURCE = "Dataverse"
    DOCUMENTATION = "https://guides.dataverse.org/en/latest/api/"

    def __init__(
        self, *, base_url: str = "https://darus.uni-stuttgart.de", timeout_s: float = 30.0
    ):
        url = httpx.URL(base_url)
        if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
            raise ValueError("base_url must be HTTPS without credentials, query or fragment")
        super().__init__(timeout_s=timeout_s)
        self.base_url = base_url.rstrip("/")

    def search(
        self,
        query: str,
        *,
        start: int = 0,
        page_size: int = 25,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Search public datasets; start is a zero-based record offset."""
        return self._json(
            f"{self.base_url}/api/search",
            params={
                "q": required_text(query, "query"),
                "type": "dataset",
                "start": bounded_int(start, "start", 0, 10_000_000),
                "per_page": bounded_int(page_size, "page_size", 1, 1000),
            },
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, status=str, data=dict),
        )

    def dataset(
        self,
        persistent_id: str,
        *,
        version: str = ":latest-published",
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Fetch published dataset metadata; pin ``version='1.0'`` for reproducibility."""
        if version != ":latest-published" and not re.fullmatch(r"\d+\.\d+", version):
            raise ValueError("version must be :latest-published or a numeric major.minor version")
        return self._json(
            f"{self.base_url}/api/datasets/:persistentId/versions/{version}",
            params={"persistentId": required_text(persistent_id, "persistent_id")},
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, status=str, data=dict),
        )

    def download_file(
        self,
        persistent_id: str,
        filename: str,
        destination: str | Path,
        *,
        version: str = ":latest-published",
        max_bytes: int = 100_000_000,
    ) -> DownloadReceipt:
        """Download the original public file and verify its dataset checksum."""
        dataset = self.dataset(persistent_id, version=version).data["data"]
        matches = [
            f for f in dataset.get("files", []) if f.get("dataFile", {}).get("filename") == filename
        ]
        if len(matches) != 1:
            raise LookupError("No unique public file with that filename")
        entry = matches[0]
        if entry.get("restricted"):
            raise PermissionError("This Dataverse file is restricted")
        file = entry["dataFile"]
        checksum = file.get("checksum", {})
        if not checksum.get("type") or not checksum.get("value"):
            raise ValueError("Dataverse file has no provider checksum")
        return self._download(
            f"{self.base_url}/api/access/datafile/{_id(file['id'])}?format=original",
            destination,
            checksum=f"{checksum['type']}:{checksum['value']}",
            max_bytes=max_bytes,
            context={
                "persistent_id": persistent_id,
                "version": f"{dataset.get('versionNumber')}.{dataset.get('versionMinorNumber')}",
                "license": dataset.get("license"),
                "termsOfUse": dataset.get("termsOfUse"),
                "filename": filename,
            },
        )


class HorizonsConnector(ResearchConnector):
    """Public NASA/JPL ephemerides for supported targets, including spacecraft.

    Returns the original JSON envelope containing the ephemeris text, headers,
    units and API signature. Vectors use ICRF axes, TDB time, geometric (no
    light-time) corrections and AU/day units. No spacecraft attitude or PV
    output is implied. Target coverage is determined by JPL.
    """

    BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
    SOURCE = "NASA/JPL Horizons"
    DOCUMENTATION = "https://ssd-api.jpl.nasa.gov/doc/horizons.html"

    def vectors(
        self,
        target: str,
        *,
        start: str,
        stop: str,
        step: str = "1 d",
        center: str = "500@10",
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Retrieve geometric vectors; default center is the Sun's center.

        Dates are YYYY-MM-DD in TDB, with both endpoints requested. The provider
        may omit the final instant if the step does not land on it. Negative
        spacecraft IDs (e.g. ``'-61'`` for Juno) avoid ambiguous name matches.
        """
        _dates(start, stop)
        if start == stop:
            raise ValueError("stop must be later than start")
        if not re.fullmatch(r"[1-9]\d* (?:m|h|d)", step):
            raise ValueError("step must be a positive integer followed by m, h or d")
        for name, value in (("target", target), ("center", center)):
            required_text(value, name)
            if any(c in value for c in "'\"\r\n"):
                raise ValueError(f"{name} must not contain quotes or newlines")

        def validate(data: Any) -> None:
            require_fields(data, result=str, signature=dict)
            if "$$SOE" not in data["result"] or "$$EOE" not in data["result"]:
                raise ValueError("Horizons returned no ephemeris; check target and coverage")

        return self._json(
            self.BASE_URL,
            params={
                "format": "json",
                "COMMAND": f"'{target}'",
                "MAKE_EPHEM": "YES",
                "EPHEM_TYPE": "VECTORS",
                "CENTER": f"'{center}'",
                "OBJ_DATA": "NO",
                "START_TIME": f"'{start}'",
                "STOP_TIME": f"'{stop}'",
                "STEP_SIZE": f"'{step}'",
                "OUT_UNITS": "AU-D",
                "REF_PLANE": "FRAME",
                "REF_SYSTEM": "ICRF",
                "TIME_TYPE": "TDB",
                "VEC_CORR": "NONE",
                "VEC_TABLE": "2",
                "CSV_FORMAT": "YES",
            },
            cache_path=cache_path,
            refresh=refresh,
            validate=validate,
        )


class PdsConnector(ResearchConnector):
    """NASA PDS Search API: mission product metadata, labels and data links.

    Archive coverage is incomplete. Retain labels to interpret product units
    and calibration; a search hit is not necessarily a power measurement.
    """

    BASE_URL = "https://pds.nasa.gov/api/search/1"
    SOURCE = "NASA PDS"
    DOCUMENTATION = "https://nasa-pds.github.io/pds-api/guides/search.html"

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        sort: str | None = None,
        search_after: str | None = None,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Search using PDS ``q`` expressions; cursor pagination requires sort.

        Example: ``'(product_class eq "Product_Bundle")'``. Use provider field
        names and operators, not SQL. The documented keywords parameter is not
        exposed: it was silently ignored by the live service in the access check.
        """
        params: dict[str, Any] = {
            "q": required_text(query, "query"),
            "limit": bounded_int(limit, "limit", 1, 1000),
        }
        if sort is not None:
            params["sort"] = required_text(sort, "sort")
        if search_after is not None:
            if sort is None:
                raise ValueError("search_after requires an explicit sort field")
            params["search-after"] = required_text(search_after, "search_after")
        return self._json(
            f"{self.BASE_URL}/products",
            params=params,
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, data=list, summary=dict),
        )

    def product(
        self,
        identifier: str,
        *,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Resolve a PDS LID or versioned LIDVID to its product metadata."""
        if not required_text(identifier, "identifier").startswith("urn:"):
            raise ValueError("identifier must be a PDS URN")
        return self._json(
            f"{self.BASE_URL}/products/{quote(identifier, safe=':')}",
            cache_path=cache_path,
            refresh=refresh,
            validate=lambda d: require_fields(d, id=str),
        )


class PsaConnector(ResearchConnector):
    """ESA Planetary Science Archive TAP/EPN-TAP read-only ADQL queries.

    JSON responses retain column names, units, types and data access links.
    ``max_records`` bounds a response; reaching it may indicate truncation.
    The service does not provide universal spacecraft EPS telemetry.
    """

    BASE_URL = "https://psa.esa.int/psa-tap/tap/sync"
    SOURCE = "ESA PSA"
    DOCUMENTATION = "https://meetingorganizer.copernicus.org/EPSC2024/EPSC2024-105.html"

    def query(
        self,
        adql: str,
        *,
        max_records: int = 100,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Run a SELECT ADQL query; results are bounded, not a complete archive."""
        if not re.match(r"^\s*SELECT\b", required_text(adql, "adql"), flags=re.IGNORECASE):
            raise ValueError("adql must be a SELECT query")

        def validate(data: Any) -> None:
            require_fields(data, metadata=list, data=list)
            if any(
                not isinstance(c, dict) or not isinstance(c.get("name"), str)
                for c in data["metadata"]
            ):
                raise ValueError("PSA column metadata is invalid")
            if any(
                not isinstance(r, list) or len(r) != len(data["metadata"]) for r in data["data"]
            ):
                raise ValueError("PSA row width does not match its column metadata")

        return self._json(
            self.BASE_URL,
            params={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "json",
                "QUERY": adql,
                "MAXREC": bounded_int(max_records, "max_records", 1, 10_000),
            },
            cache_path=cache_path,
            refresh=refresh,
            validate=validate,
        )


class DonkiConnector(ResearchConnector):
    """NASA CCMC DONKI event catalog, accessed directly without a NASA API key.

    Uses the September 2026 CCMC endpoint, not the retired kauai host. Events
    are research context, not spacecraft-specific dose or causation evidence.
    Follow CCMC's attribution and publication rules for event studies.
    """

    BASE_URL = "https://ccmc.gsfc.nasa.gov/DONKI/WS/get"
    SOURCE = "NASA CCMC DONKI"
    DOCUMENTATION = "https://ccmc.gsfc.nasa.gov/DONKI/api/"
    EVENT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"CME", "FLR", "SEP", "GST", "IPS", "MPC", "RBE", "HSS"}
    )

    def events(
        self,
        event_type: str,
        *,
        start: str,
        stop: str,
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> ResearchResponse:
        """Get an explicit UTC date window (provider endDate is inclusive).

        The raw empty response may be null or an empty list. Event links and
        associated instruments/spacecraft are kept, without assigning them to
        other missions.
        """
        if event_type not in self.EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(self.EVENT_TYPES)}")
        _dates(start, stop)

        def validate(data: Any) -> None:
            if data is not None and (
                not isinstance(data, list) or any(not isinstance(r, dict) for r in data)
            ):
                raise ValueError("DONKI did not return an event list or null")

        return self._json(
            f"{self.BASE_URL}/{event_type}",
            params={"startDate": start, "endDate": stop},
            cache_path=cache_path,
            refresh=refresh,
            validate=validate,
        )


__all__ = [
    "DataverseConnector",
    "DiscosConnector",
    "DonkiConnector",
    "HorizonsConnector",
    "NtrsConnector",
    "PdsConnector",
    "PsaConnector",
    "ZenodoConnector",
]
