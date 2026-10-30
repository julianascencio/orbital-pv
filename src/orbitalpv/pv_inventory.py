"""PV farm geometry and independently calibrated area-to-capacity methods.

Dunnett et al. (2020), DOI 10.1038/s41597-020-0469-8, and the authors'
Figshare v2 scripts (DOI 10.6084/m9.figshare.11310269.v2) motivate the
historical profile. The semantic profile distinguishes generator outlines
from plant land boundaries. Neither profile detects PV in image pixels.

The historical profile implements the published point/polygon neighbourhoods
and area proxies, with explicit geometry validation and overlap deduplication.
It does not claim to recreate the authors' historical source snapshots.
Optional geospatial libraries are loaded only when these functions are used.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

PAPER_DOI = "10.1038/s41597-020-0469-8"
PAPER_ARCHIVE_DOI = "10.6084/m9.figshare.11310269.v2"
_AREA_BASES = {"generator_panel_area", "osm_polygon_proxy", "median_polygon_imputation"}


def _geometry_libraries():
    try:
        import pyproj
        import shapely
        import shapely.geometry
        import shapely.ops
    except ImportError as exc:
        raise ImportError("PV inventory geometry requires orbital-pv[ground]") from exc
    return shapely, pyproj


def _positive(value: Any, name: str, *, zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite {'nonnegative' if zero else 'positive'} number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (result < 0 if zero else result <= 0):
        raise ValueError(f"{name} must be a finite {'nonnegative' if zero else 'positive'} number")
    return result


def _coordinates(values: Any) -> list[tuple[float, float]]:
    if not isinstance(values, list) or not values:
        raise ValueError("OSM geometry requires complete longitude/latitude coordinates")
    result = []
    for point in values:
        if not isinstance(point, Mapping):
            raise ValueError("OSM geometry has a missing coordinate")
        lon, lat = point.get("lon"), point.get("lat")
        if (
            isinstance(lon, bool)
            or isinstance(lat, bool)
            or not isinstance(lon, (float, int))
            or not isinstance(lat, (float, int))
            or not math.isfinite(lon)
            or not math.isfinite(lat)
            or not -180 <= lon <= 180
            or not -90 <= lat <= 90
        ):
            raise ValueError("OSM geometry contains invalid WGS84 coordinates")
        result.append((float(lon), float(lat)))
    if max(x for x, _ in result) - min(x for x, _ in result) > 180:
        raise ValueError("Split antimeridian-crossing geometries before inventory processing")
    return result


def _way_coordinates(element: Mapping, lookup: dict) -> list[tuple[float, float]]:
    geometry = element.get("geometry")
    if geometry is None and isinstance(element.get("nodes"), list):
        geometry = [lookup.get(("node", node)) for node in element["nodes"]]
    return _coordinates(geometry)


def _osm_geometry(element: Mapping, lookup: dict, shapely):
    kind = element["type"]
    if kind == "node":
        return shapely.geometry.Point(_coordinates([element])[0])
    if kind == "way":
        coords = _way_coordinates(element, lookup)
        if len(coords) < 4 or coords[0] != coords[-1]:
            raise ValueError("A PV way must be a closed, complete polygon")
        return shapely.geometry.Polygon(coords)
    if element.get("tags", {}).get("type") != "multipolygon":
        raise ValueError("Only multipolygon OSM relations are supported; resolve other relations")
    members = element.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("A multipolygon requires complete way members")
    roles: dict[str, list] = {"outer": [], "inner": []}
    for member in members:
        if not isinstance(member, Mapping) or member.get("type") != "way":
            raise ValueError("Resolve nested/non-way multipolygon members before processing")
        role = member.get("role", "") or "outer"
        if role not in roles:
            raise ValueError("Multipolygon way roles must be outer or inner")
        resolved = (
            member if member.get("geometry") is not None else lookup.get(("way", member.get("ref")))
        )
        if resolved is None:
            raise ValueError("Multipolygon member geometry is unavailable")
        coords = _way_coordinates(resolved, lookup)
        if len(coords) < 2:
            raise ValueError("Multipolygon member contains fewer than two coordinates")
        roles[role].append(shapely.geometry.LineString(coords))
    rings: dict[str, list] = {"outer": [], "inner": []}
    for role, lines in roles.items():
        if not lines:
            continue
        merged = shapely.ops.linemerge(lines)
        pieces = [merged] if merged.geom_type == "LineString" else list(merged.geoms)
        for ring in pieces:
            if not ring.is_ring:
                raise ValueError("Multipolygon members do not form closed, simple rings")
            rings[role].append(shapely.geometry.Polygon(ring))
    if not rings["outer"]:
        raise ValueError("Multipolygon has no outer ring")
    holes: dict[int, list] = {i: [] for i in range(len(rings["outer"]))}
    for hole in rings["inner"]:
        containers = [i for i, outer in enumerate(rings["outer"]) if outer.contains(hole)]
        if not containers:
            raise ValueError("Multipolygon inner ring is not contained by an outer ring")
        parent = min(containers, key=lambda i: rings["outer"][i].area)
        holes[parent].append(hole.exterior.coords)
    polygons = [
        shapely.geometry.Polygon(outer.exterior.coords, holes[i])
        for i, outer in enumerate(rings["outer"])
    ]
    return polygons[0] if len(polygons) == 1 else shapely.geometry.MultiPolygon(polygons)


def osm_pv_features(
    overpass: Mapping[str, Any], *, require_photovoltaic: bool = True, on_invalid: str = "raise"
) -> dict[str, Any]:
    """Convert original Overpass solar objects to validated WGS84 GeoJSON.

    Generator and plant semantics, original tags, OSM identifiers and snapshot
    time are preserved. Explicit photovoltaic method/type tags are required by
    default; unclassified solar objects can be retained with
    ``require_photovoltaic=False`` but are marked unconfirmed. Explicit solar
    thermal objects are always excluded. Nodes are points, ways must be closed,
    and multipolygon relations are assembled with member roles and holes.
    Incomplete/self-intersecting geometry raises; ``on_invalid='skip'`` records
    each exclusion in ``metadata.excluded``. No geometry is silently repaired.
    """
    if not isinstance(require_photovoltaic, bool) or on_invalid not in {"raise", "skip"}:
        raise ValueError("Use a boolean require_photovoltaic and on_invalid='raise' or 'skip'")
    if not isinstance(overpass, Mapping) or not isinstance(overpass.get("elements"), list):
        raise ValueError("Expected a raw Overpass response with an elements list")
    if overpass.get("remark"):
        raise ValueError("An incomplete Overpass response cannot be used as a PV inventory")
    shapely, _ = _geometry_libraries()
    lookup = {}
    for element in overpass["elements"]:
        if not isinstance(element, Mapping) or element.get("type") not in {
            "node",
            "way",
            "relation",
        }:
            raise ValueError("Invalid OSM element type")
        identifier = element.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            raise ValueError("OSM identifiers must be positive integers")
        key = element["type"], identifier
        if key in lookup and lookup[key] != element:
            raise ValueError("Conflicting duplicate OSM identifiers")
        lookup[key] = element
    features, excluded = [], []
    for (kind, identifier), element in sorted(lookup.items()):
        tags = element.get("tags", {})
        if not isinstance(tags, Mapping):
            raise ValueError("OSM tags must be an object")
        source_keys = ("generator:source", "plant:source", "power_source")
        if not any(tags.get(key) == "solar" for key in source_keys):
            continue
        methods = {str(tags.get(key, "")).lower() for key in ("generator:method", "plant:method")}
        types = {str(tags.get(key, "")).lower() for key in ("generator:type", "plant:type")}
        confirmed = "photovoltaic" in methods or "solar_photovoltaic_panel" in types
        source_id = f"{kind}/{identifier}"
        if any("thermal" in value for value in methods | types) or (
            require_photovoltaic and not confirmed
        ):
            excluded.append({"source_id": source_id, "reason": "not confirmed photovoltaic"})
            continue
        try:
            geometry = _osm_geometry(element, lookup, shapely)
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError(
                    "Invalid or empty PV geometry: " + shapely.is_valid_reason(geometry)
                )
        except (TypeError, ValueError) as exc:
            if on_invalid == "raise":
                raise ValueError(f"{source_id}: {exc}") from exc
            excluded.append({"source_id": source_id, "reason": str(exc)})
            continue
        power = tags.get("power")
        element_kind = power if power in {"plant", "generator"} else "unknown"
        if element_kind == "unknown":
            if tags.get("plant:source") == "solar":
                element_kind = "plant"
            elif tags.get("generator:source") == "solar":
                element_kind = "generator"
        features.append(
            {
                "type": "Feature",
                "id": source_id,
                "geometry": shapely.geometry.mapping(geometry),
                "properties": {
                    "osm_type": kind,
                    "osm_id": identifier,
                    "source_ids": [source_id],
                    "element_kind": element_kind,
                    "photovoltaic_confirmed": confirmed,
                    "tags": deepcopy(dict(tags)),
                    "geometry_source": "OpenStreetMap",
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "OpenStreetMap",
            "license": "ODbL-1.0",
            "attribution": "© OpenStreetMap contributors",
            "osm_timestamp": overpass.get("osm3s", {}).get("timestamp_osm_base"),
            "require_photovoltaic": require_photovoltaic,
            "excluded": excluded,
        },
    }


def _feature_records(features, shapely):
    if not isinstance(features, Mapping) or features.get("type") != "FeatureCollection":
        raise ValueError("Expected a WGS84 GeoJSON FeatureCollection")
    values = features.get("features")
    if not isinstance(values, list):
        raise ValueError("FeatureCollection.features must be a list")
    records, keys = [], {}
    for i, feature in enumerate(values):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise ValueError("Invalid GeoJSON feature")
        props = feature.get("properties", {})
        if not isinstance(props, Mapping):
            raise ValueError("GeoJSON feature properties must be an object")
        geometry = shapely.geometry.shape(feature.get("geometry"))
        if (
            geometry.geom_type not in {"Point", "Polygon", "MultiPolygon"}
            or geometry.is_empty
            or not geometry.is_valid
        ):
            raise ValueError("PV features must have valid Point, Polygon or MultiPolygon geometry")
        coordinates = shapely.get_coordinates(geometry)
        if (
            not np.isfinite(coordinates).all()
            or (np.abs(coordinates[:, 0]) > 180).any()
            or (np.abs(coordinates[:, 1]) > 90).any()
        ):
            raise ValueError("PV GeoJSON coordinates must be finite WGS84 longitude/latitude")
        if np.ptp(coordinates[:, 0]) > 180:
            raise ValueError("Split antimeridian-crossing geometries before clustering")
        role = props.get("element_kind", "unknown")
        if role not in {"generator", "plant", "unknown"}:
            raise ValueError("element_kind must be generator, plant or unknown")
        source_ids = props.get("source_ids", [str(feature.get("id", f"feature/{i}"))])
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or any(not isinstance(x, str) or not x for x in source_ids)
        ):
            raise ValueError("source_ids must be a nonempty list of strings")
        # Geometry duplication cannot silently turn a plant boundary into panels.
        key = role, shapely.normalize(geometry).wkb
        if key in keys:
            records[keys[key]]["source_ids"].update(source_ids)
            continue
        keys[key] = len(records)
        records.append({"geometry": geometry, "role": role, "source_ids": set(source_ids)})
    return records


def _dbscan_groups(records: list, indices: list[int], eps: float, minimum: int) -> list[list[int]]:
    if not indices:
        return []
    try:
        from sklearn.cluster import DBSCAN
    except ImportError as exc:
        raise ImportError("PV farm clustering requires orbital-pv[ground]") from exc
    coordinates = [
        (records[i]["geometry"].centroid.x, records[i]["geometry"].centroid.y) for i in indices
    ]
    labels = DBSCAN(eps=eps, min_samples=minimum).fit_predict(np.asarray(coordinates))
    groups: dict[int, list[int]] = {}
    singletons = []
    for i, label in zip(indices, labels, strict=True):
        if label < 0:
            singletons.append([i])
        else:
            groups.setdefault(int(label), []).append(i)
    return [*groups.values(), *singletons]


def _merge_overlaps(groups: list[list[int]], records: list, shapely) -> list[list[int]]:
    """Make duplicate/overlapping representations inseparable before area accounting."""
    if not groups:
        return []
    owners = {i: owner for owner, group in enumerate(groups) for i in group}
    parents = list(range(len(groups)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    indices = sorted(owners)
    geometries = [records[i]["geometry"] for i in indices]
    tree = shapely.STRtree(geometries)
    for position, geometry in enumerate(geometries):
        for neighbor in tree.query(geometry, predicate="intersects"):
            first, second = root(owners[indices[position]]), root(owners[indices[int(neighbor)]])
            if first != second:
                parents[max(first, second)] = min(first, second)
    merged: dict[int, list[int]] = {}
    for owner, group in enumerate(groups):
        merged.setdefault(root(owner), []).extend(group)
    return [sorted(set(group)) for group in merged.values()]


def cluster_pv_farms(
    features: Mapping[str, Any],
    *,
    eps_m: float = 400.0,
    min_samples: int = 2,
    keep_singletons: bool = True,
    profile: str = "semantic",
    polygon_eps_m: float | None = None,
) -> dict[str, Any]:
    """Group mapped PV features and compute nonoverlapping area measures.

    ``semantic`` clusters feature centroids at ``eps_m`` in a local equal-area
    projection, then merges intersecting geometries (including parent plants
    and their generators). ``panel_area_m2`` includes only generator polygons;
    whole-plant land area is separately recorded. Missing panel area is null.
    This local approximation requires an extent no wider than five degrees
    in either coordinate; tile broader inventories with overlapping margins.

    ``dunnett2020`` uses Eckert IV, outermost polygons, a 10 m polygon buffer
    to exclude contained/nearby points, DBSCAN at 400 m for remaining points
    and 800 m for polygon centroids by default. For point-only groups it uses
    the median input polygon area as the paper's explicit area proxy. If no
    polygon is available the proxy remains null. Intersecting output groups
    are additionally merged to prevent duplicate area, a documented safeguard
    beyond the historical script. A singleton polygon retains its original
    holes and concavities; grouped polygons use their convex hull for landscape
    area. Geometry IDs are never counted as modules.

    Outputs are WGS84 GeoJSON. ``capacity_area_m2`` and
    ``capacity_area_basis`` identify the profile's predictor separately from
    actual mapped ``panel_area_m2`` and ``osm_polygon_area_m2``. Singletons are
    retained with ``is_cluster=False`` unless explicitly excluded. This is a
    spatial grouping, not a registry of independently operated projects.
    """
    eps = _positive(eps_m, "eps_m")
    polygon_eps = _positive(
        polygon_eps_m if polygon_eps_m is not None else 2 * eps, "polygon_eps_m"
    )
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 2:
        raise ValueError("min_samples must be an integer of at least 2")
    if not isinstance(keep_singletons, bool) or profile not in {"semantic", "dunnett2020"}:
        raise ValueError("Use a boolean keep_singletons and a supported profile")
    if profile == "semantic" and polygon_eps_m is not None:
        raise ValueError("polygon_eps_m applies only to profile='dunnett2020'")
    shapely, pyproj = _geometry_libraries()
    records = _feature_records(features, shapely)
    metadata = {
        "profile": profile,
        "eps_m": eps,
        "min_samples": min_samples,
        "polygon_eps_m": polygon_eps if profile == "dunnett2020" else eps,
        "paper_doi": PAPER_DOI,
        "source_metadata": deepcopy(features.get("metadata", {})),
        "input_feature_count": len(features["features"]),
        "unique_geometry_role_count": len(records),
        "area_note": "Generator outlines and plant land are distinct; no module counts are inferred.",
    }
    if not records:
        return {"type": "FeatureCollection", "features": [], "metadata": metadata}
    all_coordinates = np.concatenate([shapely.get_coordinates(r["geometry"]) for r in records])
    if np.ptp(all_coordinates[:, 0]) > 180:
        raise ValueError("Split inventories spanning the antimeridian before clustering")
    if profile == "semantic" and np.any(np.ptp(all_coordinates, axis=0) > 5):
        raise ValueError(
            "The semantic profile uses a local projection and requires at most five degrees "
            "of longitude/latitude span; tile broader inventories with overlapping margins"
        )
    lon, lat = np.mean(all_coordinates, axis=0)
    crs = (
        "ESRI:54012"
        if profile == "dunnett2020"
        else f"+proj=laea +lat_0={lat:.10f} +lon_0={lon:.10f} +datum=WGS84 +units=m"
    )
    forward = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inverse = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    metadata["working_crs"] = crs
    for record in records:
        record["geometry"] = shapely.transform(
            record["geometry"], forward.transform, interleaved=False
        )
        if not np.isfinite(shapely.get_coordinates(record["geometry"])).all():
            raise ValueError("Features cannot be projected into the working CRS")
    polygon_indices = [i for i, r in enumerate(records) if r["geometry"].geom_type != "Point"]
    point_indices = [i for i, r in enumerate(records) if r["geometry"].geom_type == "Point"]
    attachments: dict[int, list[int]] = {}
    median_polygon_area = (
        float(np.median([records[i]["geometry"].area for i in polygon_indices]))
        if polygon_indices
        else None
    )
    if profile == "semantic":
        groups = _dbscan_groups(records, list(range(len(records))), eps, min_samples)
    else:
        # Keep outermost polygons as in the source script; retain nested IDs as provenance.
        polygon_tree = shapely.STRtree([records[i]["geometry"] for i in polygon_indices])
        outer = [
            i
            for i in polygon_indices
            if not any(
                i != j and (records[j]["geometry"].area > records[i]["geometry"].area or j < i)
                for position in polygon_tree.query(records[i]["geometry"], predicate="covered_by")
                for j in [polygon_indices[int(position)]]
            )
        ]
        outer_set = set(outer)
        outer_tree = shapely.STRtree([records[i]["geometry"] for i in outer])
        for i in polygon_indices:
            if i not in outer_set:
                parent = min(
                    (
                        outer[int(position)]
                        for position in outer_tree.query(
                            records[i]["geometry"], predicate="covered_by"
                        )
                    ),
                    key=lambda j: records[j]["geometry"].area,
                )
                attachments.setdefault(parent, []).append(i)
        remaining = []
        for i in point_indices:
            near = [
                outer[int(position)]
                for position in outer_tree.query(
                    records[i]["geometry"], predicate="dwithin", distance=10
                )
            ]
            if near:
                parent = min(
                    near, key=lambda j: (records[j]["geometry"].distance(records[i]["geometry"]), j)
                )
                attachments.setdefault(parent, []).append(i)
            else:
                remaining.append(i)
        groups = _dbscan_groups(records, outer, polygon_eps, min_samples)
        groups += _dbscan_groups(records, remaining, eps, min_samples)
    groups = _merge_overlaps(groups, records, shapely)
    output = []
    groups.sort(key=lambda group: min(source for i in group for source in records[i]["source_ids"]))
    for group in groups:
        is_cluster = len(group) >= min_samples
        if not keep_singletons and not is_cluster:
            continue
        selected = sorted(set(group) | {child for i in group for child in attachments.get(i, [])})
        generators = [
            records[i]["geometry"]
            for i in selected
            if records[i]["role"] == "generator" and records[i]["geometry"].geom_type != "Point"
        ]
        plants = [
            records[i]["geometry"]
            for i in selected
            if records[i]["role"] == "plant" and records[i]["geometry"].geom_type != "Point"
        ]
        polygons = [
            records[i]["geometry"] for i in selected if records[i]["geometry"].geom_type != "Point"
        ]
        panel_area = float(shapely.union_all(generators).area) if generators else None
        polygon_area = float(shapely.union_all(polygons).area) if polygons else None
        geometry = shapely.union_all([records[i]["geometry"] for i in group])
        landscape = geometry.convex_hull
        if profile == "dunnett2020" and len(group) == 1 and polygons:
            # The original pol.solo branch keeps its polygon, including holes
            # and concavities; only grouped polygons use a convex hull.
            landscape = geometry
        if profile == "dunnett2020" and not polygons and len(group) > 1:
            landscape = landscape.buffer(1)
        if profile == "semantic":
            capacity_area, basis = panel_area, "generator_panel_area"
        elif polygons:
            capacity_area, basis = polygon_area, "osm_polygon_proxy"
        else:
            capacity_area = (
                None if median_polygon_area is None else len(group) * median_polygon_area
            )
            basis = "median_polygon_imputation"
        centroid = shapely.transform(geometry.centroid, inverse.transform, interleaved=False)
        source_ids = sorted({source for i in selected for source in records[i]["source_ids"]})
        output.append(
            {
                "type": "Feature",
                "id": f"farm/{len(output) + 1}",
                "geometry": shapely.geometry.mapping(
                    shapely.transform(landscape, inverse.transform, interleaved=False)
                ),
                "properties": {
                    "source_ids": source_ids,
                    "source_feature_count": len(source_ids),
                    "unique_geometry_role_count": len(selected),
                    "is_cluster": is_cluster,
                    "generator_feature_count": sum(
                        records[i]["role"] == "generator" for i in selected
                    ),
                    "plant_feature_count": sum(records[i]["role"] == "plant" for i in selected),
                    "point_feature_count": sum(
                        records[i]["geometry"].geom_type == "Point" for i in selected
                    ),
                    "panel_area_m2": panel_area,
                    "osm_polygon_area_m2": polygon_area,
                    "plant_area_m2": float(shapely.union_all(plants).area) if plants else None,
                    "landscape_area_m2": float(landscape.area),
                    "capacity_area_m2": capacity_area,
                    "capacity_area_basis": basis,
                    "centroid_lon": float(centroid.x),
                    "centroid_lat": float(centroid.y),
                    "profile": profile,
                    "geometry_source": "grouped source features",
                },
            }
        )
    return {"type": "FeatureCollection", "features": output, "metadata": metadata}


def _numeric_vector(values: Any, name: str) -> np.ndarray:
    raw = np.asarray(values)
    if raw.dtype.kind in "bc" or raw.ndim != 1 or raw.size == 0:
        raise ValueError(f"{name} must be a nonempty one-dimensional array of real numbers")
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must contain real numbers") from exc
    if not np.isfinite(array).all() or (array <= 0).any():
        raise ValueError(f"{name} must contain finite positive numbers")
    return array


def _urban_flags(values: Sequence[bool | None] | np.ndarray, size: int) -> np.ndarray:
    if isinstance(values, (str, bytes)) or len(values) != size:
        raise ValueError("urban must contain one explicit boolean or None per observation")
    if any(value is not None and not isinstance(value, (bool, np.bool_)) for value in values):
        raise ValueError("urban must contain booleans or None; unknown is not nonurban")
    return np.asarray([value is not None and not bool(value) for value in values], dtype=bool)


def _boxcox(values: np.ndarray, exponent: float) -> np.ndarray:
    return np.log(values) if exponent == 0 else np.expm1(exponent * np.log(values)) / exponent


@dataclass(frozen=True, slots=True)
class PVCapacityPrediction:
    """Conditional MW estimates and approximate Gaussian prediction intervals.

    Ineligible or disallowed extrapolated estimates are NaN. Intervals include
    residual variance and fitted-coefficient uncertainty using a local
    linearization; they do not include mapping error, uncertain area/labels,
    Box-Cox parameter uncertainty, or geographic/technology domain shift.
    Their nominal coverage is not a guarantee on a new country or sensor.
    """

    mean_mw: np.ndarray
    lower_mw: np.ndarray
    upper_mw: np.ndarray
    eligible: np.ndarray
    extrapolated: np.ndarray
    reasons: tuple[str, ...]
    confidence: float
    capacity_basis: str
    area_basis: str


@dataclass(frozen=True, slots=True)
class PVCapacityModel:
    """A newly calibrated Gaussian-log-link area model, with source provenance.

    The model form follows the published R script: transform positive area in
    km² with Box-Cox, divide by sample standard deviation, then fit
    ``E[capacity_MW] = exp(intercept + slope * transformed_area / scale)``.
    Preprocessing is fitted only on the supplied calibration observations.
    Lambda maximizes the Box-Cox normal likelihood over [-3, 3], with caret's
    0.2 tolerance around zero and one. Continuous optimization and nonlinear
    least squares can differ numerically from R's grid/IRLS implementation.
    This is a recalibration, not the original authors' trained model.
    """

    boxcox_lambda: float
    area_scale: float
    intercept: float
    slope: float
    coefficient_covariance: tuple[tuple[float, float], tuple[float, float]]
    residual_std_mw: float
    training_area_range_m2: tuple[float, float]
    training_capacity_range_mw: tuple[float, float]
    n_training: int
    n_excluded: int
    min_area_m2: float
    capacity_basis: str
    area_basis: str
    source: str
    fit_rmse_mw: float
    fit_mae_mw: float

    def predict(
        self,
        area_m2: ArrayLike,
        *,
        urban: Sequence[bool | None] | np.ndarray,
        area_basis: str,
        allow_extrapolation: bool = False,
        confidence: float = 0.95,
    ) -> PVCapacityPrediction:
        """Predict for matching area semantics, flagging unsupported observations.

        Only explicitly nonurban observations above ``min_area_m2`` qualify.
        Extrapolation outside the calibration area range is withheld by
        default and remains flagged when explicitly allowed. The caller must
        use the same area definition and AC/DC/reported capacity basis as the
        calibration data. Urban status can come from a declared GHSL edition.
        """
        if area_basis != self.area_basis:
            raise ValueError("Prediction area_basis must match the calibrated area definition")
        if not isinstance(allow_extrapolation, bool):
            raise ValueError("allow_extrapolation must be a boolean")
        confidence = _positive(confidence, "confidence")
        if confidence >= 1:
            raise ValueError("confidence must lie strictly between zero and one")
        areas = _numeric_vector(area_m2, "area_m2")
        nonurban = _urban_flags(urban, areas.size)
        extrapolated = (areas < self.training_area_range_m2[0]) | (
            areas > self.training_area_range_m2[1]
        )
        eligible = nonurban & (areas > self.min_area_m2) & (~extrapolated | allow_extrapolation)
        reasons = tuple(
            "urban_or_unknown"
            if not nonurban[i]
            else "area_below_domain"
            if areas[i] <= self.min_area_m2
            else "extrapolation_withheld"
            if extrapolated[i] and not allow_extrapolation
            else "extrapolation_allowed"
            if extrapolated[i]
            else "within_calibration_range"
            for i in range(areas.size)
        )
        mean = np.full(areas.shape, np.nan)
        lower, upper = mean.copy(), mean.copy()
        if eligible.any():
            from scipy.stats import t

            z = _boxcox(areas[eligible] / 1_000_000, self.boxcox_lambda) / self.area_scale
            linear = self.intercept + self.slope * z
            if not np.isfinite(linear).all() or (linear > math.log(np.finfo(float).max)).any():
                raise ValueError("Capacity extrapolation exceeds the numerical range")
            predicted = np.exp(linear)
            jacobian = predicted[:, None] * np.column_stack((np.ones(z.size), z))
            covariance = np.asarray(self.coefficient_covariance)
            variance = self.residual_std_mw**2 + np.einsum(
                "ij,jk,ik->i", jacobian, covariance, jacobian
            )
            width = float(t.ppf((1 + confidence) / 2, self.n_training - 2)) * np.sqrt(
                np.maximum(0, variance)
            )
            mean[eligible] = predicted
            lower[eligible] = np.maximum(0, predicted - width)
            upper[eligible] = predicted + width
        return PVCapacityPrediction(
            mean,
            lower,
            upper,
            eligible,
            extrapolated,
            reasons,
            confidence,
            self.capacity_basis,
            self.area_basis,
        )


def fit_pv_capacity_model(
    area_m2: ArrayLike,
    capacity_mw: ArrayLike,
    *,
    urban: Sequence[bool | None] | np.ndarray,
    capacity_basis: str,
    area_basis: str,
    source: str,
    min_area_m2: float = 10_000.0,
    max_capacity_mw: float | None = 1000.0,
) -> PVCapacityModel:
    """Calibrate the paper's area-only model form from independent capacities.

    Inputs are matched observations: area in m², capacity in MW, and explicit
    urban flags. The default domain mirrors the source script (>1 ha,
    nonurban, capacity <1000 MW). Set the capacity ceiling explicitly for a
    modern calibration; 1000 MW is a historical outlier cutoff, not a physical
    limit. Exclusions are counted. At least six retained observations and
    three distinct areas are required. A sample is not an independent test:
    evaluate on held-out sites/countries separately.

    ``capacity_basis`` must be 'AC', 'DC', or 'reported'; ``area_basis`` must
    declare generator panel area, an OSM polygon proxy, or a median polygon
    imputation. Never mix total site land with module/array surface area in a
    single calibration. The nonempty ``source`` describes external capacity
    evidence; this function cannot verify that provenance automatically.
    """
    from scipy.optimize import least_squares, minimize_scalar
    from scipy.stats import boxcox_llf

    areas = _numeric_vector(area_m2, "area_m2")
    capacities = _numeric_vector(capacity_mw, "capacity_mw")
    if areas.shape != capacities.shape:
        raise ValueError("Area and capacity arrays must have equal length")
    nonurban = _urban_flags(urban, areas.size)
    minimum = _positive(min_area_m2, "min_area_m2", zero=True)
    maximum = None if max_capacity_mw is None else _positive(max_capacity_mw, "max_capacity_mw")
    if capacity_basis not in {"AC", "DC", "reported"} or area_basis not in _AREA_BASES:
        raise ValueError("Declare a supported capacity_basis and area_basis")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Calibration requires a nonempty independent data source description")
    keep = nonurban & (areas > minimum)
    if maximum is not None:
        keep &= capacities < maximum
    selected_areas, observed = areas[keep], capacities[keep]
    if selected_areas.size < 6 or np.unique(selected_areas).size < 3:
        raise ValueError(
            "Calibration requires at least six eligible records and three distinct areas"
        )
    area_km2 = selected_areas / 1_000_000
    optimized = minimize_scalar(
        lambda exponent: -float(boxcox_llf(exponent, area_km2)), bounds=(-3, 3), method="bounded"
    )
    if not optimized.success or not math.isfinite(optimized.x):
        raise ValueError("Box-Cox calibration did not converge")
    exponent = float(optimized.x)
    if abs(exponent) <= 0.2:
        exponent = 0.0
    elif abs(exponent - 1) <= 0.2:
        exponent = 1.0
    transformed = _boxcox(area_km2, exponent)
    scale = float(np.std(transformed, ddof=1))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Transformed calibration area has no finite variation")
    z = transformed / scale
    design = np.column_stack((np.ones(z.size), z))
    initial = np.linalg.lstsq(design, np.log(observed), rcond=None)[0]

    def mean(parameters):
        eta = design @ parameters
        # Reject numerical overflow before it corrupts the optimizer's residuals.
        return np.exp(np.clip(eta, -300, 300))

    fitted = least_squares(
        lambda parameters: mean(parameters) - observed,
        initial,
        jac=lambda parameters: mean(parameters)[:, None] * design,
        max_nfev=3000,
        ftol=1e-11,
        xtol=1e-11,
        gtol=1e-11,
    )
    if not fitted.success or not np.isfinite(fitted.x).all() or fitted.x[1] <= 0:
        raise ValueError("Capacity calibration failed or produced a non-increasing area relation")
    residual = mean(fitted.x) - observed
    variance = float(np.dot(residual, residual) / (observed.size - 2))
    information = fitted.jac.T @ fitted.jac
    if np.linalg.matrix_rank(information) < 2:
        raise ValueError("Capacity calibration is numerically unidentifiable")
    covariance = variance * np.linalg.inv(information)
    return PVCapacityModel(
        boxcox_lambda=exponent,
        area_scale=scale,
        intercept=float(fitted.x[0]),
        slope=float(fitted.x[1]),
        coefficient_covariance=(
            (float(covariance[0, 0]), float(covariance[0, 1])),
            (float(covariance[1, 0]), float(covariance[1, 1])),
        ),
        residual_std_mw=math.sqrt(variance),
        training_area_range_m2=(float(selected_areas.min()), float(selected_areas.max())),
        training_capacity_range_mw=(float(observed.min()), float(observed.max())),
        n_training=observed.size,
        n_excluded=int((~keep).sum()),
        min_area_m2=minimum,
        capacity_basis=capacity_basis,
        area_basis=area_basis,
        source=source.strip(),
        fit_rmse_mw=float(np.sqrt(np.mean(residual**2))),
        fit_mae_mw=float(np.mean(np.abs(residual))),
    )


def evaluate_pv_capacity(
    observed_mw: ArrayLike, prediction: PVCapacityPrediction
) -> dict[str, Any]:
    """Report held-out error and interval coverage without hiding exclusions.

    Caller-supplied observations must be independent of fitting and use the
    model's declared capacity basis. Counts include withheld/extrapolated
    predictions, while metrics use only eligible finite estimates. R² is null
    for a constant reference; no eligible predictions produces null metrics.
    """
    observed = _numeric_vector(observed_mw, "observed_mw")
    if observed.shape != prediction.mean_mw.shape:
        raise ValueError("Observed and predicted capacities must have equal shape")
    valid = prediction.eligible & np.isfinite(prediction.mean_mw)
    result: dict[str, Any] = {
        "n_total": observed.size,
        "n_evaluated": int(valid.sum()),
        "n_withheld": int((~valid).sum()),
        "n_extrapolated": int(prediction.extrapolated.sum()),
        "rmse_mw": None,
        "mae_mw": None,
        "bias_mw": None,
        "r2": None,
        "interval_coverage": None,
        "nominal_confidence": prediction.confidence,
        "capacity_basis": prediction.capacity_basis,
        "area_basis": prediction.area_basis,
    }
    if valid.any():
        actual, predicted = observed[valid], prediction.mean_mw[valid]
        error = predicted - actual
        denominator = float(np.sum((actual - actual.mean()) ** 2))
        result.update(
            rmse_mw=float(np.sqrt(np.mean(error**2))),
            mae_mw=float(np.mean(np.abs(error))),
            bias_mw=float(error.mean()),
            r2=1 - float(np.sum(error**2)) / denominator if denominator > 0 else None,
            interval_coverage=float(
                np.mean(
                    (actual >= prediction.lower_mw[valid]) & (actual <= prediction.upper_mw[valid])
                )
            ),
        )
    return result
