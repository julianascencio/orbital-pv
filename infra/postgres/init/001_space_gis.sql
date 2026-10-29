CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS gis;

CREATE TABLE IF NOT EXISTS catalog.satellites (
    id TEXT PRIMARY KEY,
    norad_id BIGINT UNIQUE,
    cospar_id TEXT,
    name TEXT NOT NULL,
    object_type TEXT,
    mission TEXT,
    source TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_satellites_name ON catalog.satellites (name);
CREATE INDEX IF NOT EXISTS ix_satellites_norad_id ON catalog.satellites (norad_id);

CREATE TABLE IF NOT EXISTS gis.satellite_latest_state (
    satellite_id TEXT PRIMARY KEY REFERENCES catalog.satellites(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    longitude_deg DOUBLE PRECISION NOT NULL CHECK (longitude_deg >= -180 AND longitude_deg <= 180),
    latitude_deg DOUBLE PRECISION NOT NULL CHECK (latitude_deg >= -90 AND latitude_deg <= 90),
    altitude_m DOUBLE PRECISION NOT NULL,
    ecef_x_m DOUBLE PRECISION,
    ecef_y_m DOUBLE PRECISION,
    ecef_z_m DOUBLE PRECISION,
    velocity_x_m_s DOUBLE PRECISION,
    velocity_y_m_s DOUBLE PRECISION,
    velocity_z_m_s DOUBLE PRECISION,
    illumination_fraction DOUBLE PRECISION,
    pv_power_w DOUBLE PRECISION,
    source TEXT NOT NULL,
    position geometry(POINTZ, 4979) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_satellite_latest_state_position ON gis.satellite_latest_state USING GIST (position);
CREATE INDEX IF NOT EXISTS ix_satellite_latest_state_observed_at ON gis.satellite_latest_state (observed_at DESC);

CREATE TABLE IF NOT EXISTS gis.orbit_track_segments (
    id TEXT PRIMARY KEY,
    satellite_id TEXT NOT NULL REFERENCES catalog.satellites(id) ON DELETE CASCADE,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    lod SMALLINT NOT NULL DEFAULT 1,
    sample_interval_s INTEGER NOT NULL,
    point_count INTEGER NOT NULL,
    samples JSONB NOT NULL,
    ground_track geometry(MULTILINESTRING, 4326) NOT NULL,
    source TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_at > start_at),
    CHECK (point_count > 1)
);
CREATE INDEX IF NOT EXISTS ix_orbit_track_segment_time ON gis.orbit_track_segments (satellite_id, start_at, end_at, lod);
CREATE INDEX IF NOT EXISTS ix_orbit_track_segment_ground_track ON gis.orbit_track_segments USING GIST (ground_track);
CREATE INDEX IF NOT EXISTS ix_orbit_track_segment_expires ON gis.orbit_track_segments (expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS gis.ground_stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    longitude_deg DOUBLE PRECISION NOT NULL,
    latitude_deg DOUBLE PRECISION NOT NULL,
    altitude_m DOUBLE PRECISION NOT NULL DEFAULT 0,
    station geometry(POINT, 4326) NOT NULL,
    source TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_ground_stations_station ON gis.ground_stations USING GIST (station);

CREATE TABLE IF NOT EXISTS gis.coverage_footprints (
    id TEXT PRIMARY KEY,
    satellite_id TEXT NOT NULL REFERENCES catalog.satellites(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    footprint geometry(MULTIPOLYGON, 4326) NOT NULL,
    source TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_coverage_footprints_time ON gis.coverage_footprints (satellite_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS ix_coverage_footprints_geom ON gis.coverage_footprints USING GIST (footprint);
