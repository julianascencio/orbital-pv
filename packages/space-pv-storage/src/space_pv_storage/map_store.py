from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_latest_satellite_states(session: Session, limit: int = 2000) -> list[dict[str, Any]]:
    statement = text("""
        SELECT s.id AS satellite_id, s.name, s.norad_id, st.observed_at,
               st.longitude_deg, st.latitude_deg, st.altitude_m,
               st.illumination_fraction, st.pv_power_w, st.source
        FROM gis.satellite_latest_state st
        JOIN catalog.satellites s ON s.id = st.satellite_id
        ORDER BY st.observed_at DESC
        LIMIT :limit
        """)
    return [dict(row) for row in session.execute(statement, {"limit": limit}).mappings()]


def get_track_samples(
    session: Session, satellite_id: str, start_at: datetime, end_at: datetime, lod: int = 1
) -> list[dict[str, Any]]:
    statement = text("""
        SELECT id, start_at, end_at, lod, sample_interval_s, point_count, samples, source
        FROM gis.orbit_track_segments
        WHERE satellite_id = :satellite_id AND lod = :lod
          AND end_at >= :start_at AND start_at <= :end_at
        ORDER BY start_at
        """)
    return [
        dict(row)
        for row in session.execute(
            statement,
            {"satellite_id": satellite_id, "start_at": start_at, "end_at": end_at, "lod": lod},
        ).mappings()
    ]


def upsert_latest_satellite_state(
    session: Session,
    *,
    satellite_id: str,
    observed_at: datetime,
    longitude_deg: float,
    latitude_deg: float,
    altitude_m: float,
    source: str,
    ecef_m: tuple[float, float, float] | None = None,
    velocity_m_s: tuple[float, float, float] | None = None,
    illumination_fraction: float | None = None,
    pv_power_w: float | None = None,
) -> None:
    ecef = ecef_m or (None, None, None)
    velocity = velocity_m_s or (None, None, None)
    statement = text("""
        INSERT INTO gis.satellite_latest_state (
            satellite_id, observed_at, longitude_deg, latitude_deg, altitude_m,
            ecef_x_m, ecef_y_m, ecef_z_m, velocity_x_m_s, velocity_y_m_s, velocity_z_m_s,
            illumination_fraction, pv_power_w, source, position, updated_at
        ) VALUES (
            :satellite_id, :observed_at, :longitude_deg, :latitude_deg, :altitude_m,
            :ecef_x_m, :ecef_y_m, :ecef_z_m, :velocity_x_m_s, :velocity_y_m_s, :velocity_z_m_s,
            :illumination_fraction, :pv_power_w, :source,
            ST_SetSRID(ST_MakePoint(:longitude_deg, :latitude_deg, :altitude_m), 4979), now()
        )
        ON CONFLICT (satellite_id) DO UPDATE SET
            observed_at=EXCLUDED.observed_at, longitude_deg=EXCLUDED.longitude_deg,
            latitude_deg=EXCLUDED.latitude_deg, altitude_m=EXCLUDED.altitude_m,
            ecef_x_m=EXCLUDED.ecef_x_m, ecef_y_m=EXCLUDED.ecef_y_m, ecef_z_m=EXCLUDED.ecef_z_m,
            velocity_x_m_s=EXCLUDED.velocity_x_m_s, velocity_y_m_s=EXCLUDED.velocity_y_m_s, velocity_z_m_s=EXCLUDED.velocity_z_m_s,
            illumination_fraction=EXCLUDED.illumination_fraction, pv_power_w=EXCLUDED.pv_power_w,
            source=EXCLUDED.source, position=EXCLUDED.position, updated_at=now()
        """)
    session.execute(
        statement,
        {
            "satellite_id": satellite_id,
            "observed_at": observed_at,
            "longitude_deg": longitude_deg,
            "latitude_deg": latitude_deg,
            "altitude_m": altitude_m,
            "ecef_x_m": ecef[0],
            "ecef_y_m": ecef[1],
            "ecef_z_m": ecef[2],
            "velocity_x_m_s": velocity[0],
            "velocity_y_m_s": velocity[1],
            "velocity_z_m_s": velocity[2],
            "illumination_fraction": illumination_fraction,
            "pv_power_w": pv_power_w,
            "source": source,
        },
    )
    session.commit()


def upsert_satellite_catalog(
    session: Session,
    *,
    satellite_id: str,
    name: str,
    norad_id: int | None = None,
    cospar_id: str | None = None,
    object_type: str | None = None,
    mission: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    import json

    statement = text("""
        INSERT INTO catalog.satellites (id,norad_id,cospar_id,name,object_type,mission,source,metadata)
        VALUES (:id,:norad_id,:cospar_id,:name,:object_type,:mission,:source,CAST(:metadata AS jsonb))
        ON CONFLICT (id) DO UPDATE SET norad_id=EXCLUDED.norad_id, cospar_id=EXCLUDED.cospar_id,
        name=EXCLUDED.name, object_type=EXCLUDED.object_type, mission=EXCLUDED.mission,
        source=EXCLUDED.source, metadata=EXCLUDED.metadata, updated_at=now()
        """)
    session.execute(
        statement,
        {
            "id": satellite_id,
            "norad_id": norad_id,
            "cospar_id": cospar_id,
            "name": name,
            "object_type": object_type,
            "mission": mission,
            "source": source,
            "metadata": json.dumps(metadata or {}),
        },
    )
    session.commit()


def _split_antimeridian(
    samples: list[tuple[float, float, float, float]],
) -> list[list[tuple[float, float]]]:
    if len(samples) < 2:
        raise ValueError("at least two samples are required")
    parts: list[list[tuple[float, float]]] = [[]]
    previous_lon = None
    for _, lon, lat, _ in samples:
        if previous_lon is not None and abs(lon - previous_lon) > 180.0:
            parts.append([])
        parts[-1].append((lon, lat))
        previous_lon = lon
    return [part for part in parts if len(part) >= 2]


def write_track_segment(
    session: Session,
    *,
    segment_id: str,
    satellite_id: str,
    start_at: datetime,
    end_at: datetime,
    samples: list[tuple[float, float, float, float]],
    sample_interval_s: int,
    lod: int,
    source: str,
    expires_at: datetime | None = None,
) -> None:
    if end_at <= start_at:
        raise ValueError("end_at must be after start_at")
    if len(samples) < 2:
        raise ValueError("at least two samples are required")
    parts = _split_antimeridian(samples)
    if not parts:
        raise ValueError("track does not contain a drawable segment")

    def line(part):
        return "(" + ",".join(f"{lon:.9f} {lat:.9f}" for lon, lat in part) + ")"

    wkt = "MULTILINESTRING(" + ",".join(line(part) for part in parts) + ")"
    import json

    statement = text("""
        INSERT INTO gis.orbit_track_segments (id,satellite_id,start_at,end_at,lod,sample_interval_s,point_count,samples,ground_track,source,expires_at)
        VALUES (:id,:satellite_id,:start_at,:end_at,:lod,:sample_interval_s,:point_count,CAST(:samples AS jsonb),ST_GeomFromText(:wkt,4326),:source,:expires_at)
        ON CONFLICT (id) DO UPDATE SET start_at=EXCLUDED.start_at,end_at=EXCLUDED.end_at,lod=EXCLUDED.lod,
        sample_interval_s=EXCLUDED.sample_interval_s,point_count=EXCLUDED.point_count,samples=EXCLUDED.samples,
        ground_track=EXCLUDED.ground_track,source=EXCLUDED.source,expires_at=EXCLUDED.expires_at
        """)
    session.execute(
        statement,
        {
            "id": segment_id,
            "satellite_id": satellite_id,
            "start_at": start_at,
            "end_at": end_at,
            "lod": lod,
            "sample_interval_s": sample_interval_s,
            "point_count": len(samples),
            "samples": json.dumps(samples),
            "wkt": wkt,
            "source": source,
            "expires_at": expires_at,
        },
    )
    session.commit()
