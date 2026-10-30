"""Ground energy features from OpenStreetMap's public Overpass API.

The primary source-tag selection follows Dunnett et al. (2020),
https://doi.org/10.1038/s41597-020-0469-8. The raw extract is not a reproduction
of their historical database, spatial clustering, or capacity estimates.
OpenStreetMap data are © OpenStreetMap contributors, licensed under ODbL:
https://www.openstreetmap.org/copyright.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .http_base import HttpConnector


def _bounded_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    if isinstance(bbox, (str, bytes)) or len(bbox) != 4:
        raise ValueError("bbox must contain (west, south, east, north) in WGS84 degrees")
    try:
        if any(isinstance(value, bool) for value in bbox):
            raise ValueError
        west, south, east, north = (float(value) for value in bbox)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("bbox coordinates must be finite numbers") from exc
    if not all(math.isfinite(value) for value in (west, south, east, north)):
        raise ValueError("bbox coordinates must be finite numbers")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(
            "bbox must satisfy -180 <= west < east <= 180 and -90 <= south < north <= 90; "
            "split antimeridian-crossing regions into separate requests"
        )
    if (east - west) * (north - south) > 1.0:
        raise ValueError(
            "Overpass requests are limited to 1 square degree; use smaller regions or "
            "a regional OSM extract for large-area work"
        )
    return west, south, east, north


def _validate_response(content: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Overpass response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Overpass response must be a JSON object")
    if payload.get("remark"):
        raise RuntimeError(
            f"Overpass returned an incomplete or failed response: {str(payload['remark'])[:500]}"
        )
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass response must contain an elements list")
    for element in elements:
        if (
            not isinstance(element, dict)
            or not isinstance(element.get("type"), str)
            or element.get("type") not in {"node", "way", "relation"}
            or not isinstance(element.get("id"), int)
            or isinstance(element["id"], bool)
            or element["id"] <= 0
        ):
            raise ValueError("Overpass elements must have an OSM node/way/relation type and id")
        if "tags" in element and not isinstance(element["tags"], dict):
            raise ValueError("Overpass element tags must be an object")
    return payload


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class OpenStreetMapEnergyConnector(HttpConnector):
    """Retrieve small-area raw solar/wind features with original OSM structure.

    ``generator:source`` and ``plant:source`` select the paper's input features
    without requiring a second ``power`` tag. For older tagging, the query also
    includes ``power_source`` on ``power=generator`` or ``power=plant`` objects.
    This additional legacy selection is explicit and is not an exact replay of
    the paper's 2020 search. ``solar`` can include solar thermal: inspect the
    source's method/type tags before treating features as photovoltaic arrays.

    The result is Overpass JSON, not GeoJSON. Nodes, way-node references, all
    tags, relation member roles and available geometry are preserved. The query
    requests full geometry rather than clipping outlines at the bounding box.
    A way/relation can therefore extend beyond the requested region. Nested
    relation references remain references and may need additional resolution.
    No polygon merging, geometry repair, capacity parsing or clustering occurs.

    The current snapshot and source timestamp are retained. The optional cache
    stores original response bytes and a ``.meta.json`` sidecar containing the
    query, retrieval time, license and SHA-256. Public Overpass availability and
    rate limits apply; global extraction belongs in a regional/planet workflow.
    """

    API = "https://overpass-api.de/api/interpreter"

    def fetch_energy_features(
        self,
        *,
        bbox: Sequence[float],
        sources: Sequence[str] = ("solar", "wind"),
        cache_path: str | Path | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Return the raw source-tagged nodes, ways and relations for a region.

        Parameters
        ----------
        bbox : sequence of float
            ``(west, south, east, north)`` in WGS84 longitude/latitude degrees.
            At most one square degree is allowed. Antimeridian-crossing regions
            must be split into separate boxes. This is a feature-selection box,
            not an exact polygon-intersection test or an output-geometry clip.
        sources : sequence of str
            Any nonempty subset of ``("solar", "wind")``. Input order and
            duplicate values do not change the query or cache identity.
        cache_path : str or pathlib.Path, optional
            Original Overpass JSON cache. An existing cache must match both the
            complete query and its recorded checksum; mismatches raise errors.
        refresh : bool
            Fetch a new snapshot and replace the cache only after a valid,
            complete response has been received. Defaults to offline cache reuse.

        Returns
        -------
        dict
            Original decoded Overpass object, including ``elements`` and source
            metadata such as ``osm3s.timestamp_osm_base`` when provided. An empty
            elements list is a valid result; provider errors are never converted
            into an empty dataset.
        """
        west, south, east, north = _bounded_bbox(bbox)
        if (
            isinstance(sources, (str, bytes))
            or not sources
            or any(
                not isinstance(source, str) or source not in {"solar", "wind"} for source in sources
            )
        ):
            raise ValueError("sources must contain only 'solar' and/or 'wind'")
        selected = sorted(set(sources))
        # Overpass uses south, west, north, east, unlike the public bbox argument.
        area = ",".join(format(value, ".15g") for value in (south, west, north, east))
        selectors = []
        for source in selected:
            selectors.extend(
                [
                    f'  nwr["generator:source"="{source}"]({area});',
                    f'  nwr["plant:source"="{source}"]({area});',
                    f'  nwr["power"~"^(generator|plant)$"]["power_source"="{source}"]({area});',
                ]
            )
        query = "[out:json][timeout:25];\n(\n" + "\n".join(selectors) + "\n);\nout body geom;"
        request = {
            "endpoint": self.API,
            "bbox": [west, south, east, north],
            "sources": selected,
            "query": query,
        }
        path = Path(cache_path) if cache_path is not None else None
        sidecar = path.with_suffix(path.suffix + ".meta.json") if path is not None else None
        if path is not None and path.exists() and not refresh:
            if sidecar is None or not sidecar.exists():
                raise ValueError("Overpass cache has no provenance sidecar; use refresh=True")
            try:
                provenance = json.loads(sidecar.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("Overpass cache provenance is not valid JSON") from exc
            if not isinstance(provenance, dict) or provenance.get("request") != request:
                raise ValueError(
                    "Overpass cache belongs to a different query; use a new cache path"
                )
            content = path.read_bytes()
            if provenance.get("sha256") != sha256(content).hexdigest():
                raise ValueError("Overpass cache SHA-256 does not match its provenance sidecar")
            return _validate_response(content)

        response = self._client.post(self.API, data={"data": query})
        response.raise_for_status()
        content = response.content
        payload = _validate_response(content)
        if path is not None and sidecar is not None:
            provenance = {
                **asdict(
                    self.receipt(
                        "OpenStreetMap / Overpass API", str(response.url), content, path=path
                    )
                ),
                "request": request,
                "license": "ODbL-1.0",
                "attribution": "© OpenStreetMap contributors",
                "license_url": "https://www.openstreetmap.org/copyright",
                "paper_doi": "10.1038/s41597-020-0469-8",
                "parser_version": "1",
            }
            _atomic_write(path, content)
            _atomic_write(sidecar, (json.dumps(provenance, indent=2) + "\n").encode("utf-8"))
        return payload
