import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getDemoMapScene,
  getHealth,
  getLiveMapScene,
  getLiveTrack,
} from "./api";
import type { Group } from "./api";
import { SpaceGlobe } from "./components/SpaceGlobe";
import { illuminationLabel, sampleAt } from "./tracking";

export default function App() {
  const [mode, setMode] = useState<"live" | "demo">("live");
  const [group, setGroup] = useState<Group>("stations");
  const [idInput, setIdInput] = useState("");
  const [noradId, setNoradId] = useState<number>();
  const [selectedId, setSelectedId] = useState<string>();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 30000,
  });
  const scene = useQuery({
    queryKey: ["map", mode, group, noradId],
    queryFn: () =>
      mode === "live" ? getLiveMapScene(group, noradId) : getDemoMapScene(),
    retry: false,
    refetchInterval: mode === "live" ? 60000 : false,
    refetchOnWindowFocus: false,
  });
  const selected =
    scene.data?.tracks.find((t) => t.satellite_id === selectedId) ??
    scene.data?.tracks[0];
  const track = useQuery({
    queryKey: ["live-track", mode, selected?.satellite_id, group, noradId],
    queryFn: () =>
      getLiveTrack(selected!.satellite_id, group, noradId !== undefined),
    enabled: mode === "live" && !!selected,
    retry: false,
    refetchInterval: 300000,
    refetchOnWindowFocus: false,
  });
  const sample =
    mode === "live" && selected ? sampleAt(selected.samples, now) : undefined;
  const ageHours = selected?.element_epoch
    ? (now - Date.parse(selected.element_epoch)) / 3600000
    : null;
  const expired = mode === "live" && !!selected && !sample;
  const timestamp = (value?: string | null) =>
    value
      ? new Date(value)
          .toISOString()
          .replace("T", " ")
          .replace(/\.\d{3}Z$/, " UTC")
      : "Unavailable";

  return (
    <main className="shell">
      <header className="hero compact">
        <div className="topline">
          <p className="eyebrow">ORBITAL PV / MISSION VIEW</p>
          <span className="status">
            <span
              className={health.data?.status === "ok" ? "dot online" : "dot"}
            />
            API {health.data?.status === "ok" ? "connected" : "offline"}
          </span>
        </div>
        <h1>Satellites, in motion.</h1>
        <p className="lede">
          Explore current orbital positions, ground tracks and sunlight
          exposure.
        </p>
      </header>
      <section className="map-panel">
        <div className="map-panel-head">
          <div className="mode-tabs" aria-label="Data mode">
            <button
              aria-pressed={mode === "live"}
              onClick={() => setMode("live")}
            >
              Live predictions
            </button>
            <button
              aria-pressed={mode === "demo"}
              onClick={() => setMode("demo")}
            >
              Synthetic demo
            </button>
          </div>
          <time className="utc-clock">
            {timestamp(new Date(now).toISOString())}
          </time>
        </div>
        {mode === "live" && (
          <form
            className="controls"
            onSubmit={(event) => {
              event.preventDefault();
              setNoradId(idInput.trim() ? Number(idInput) : undefined);
              setSelectedId(undefined);
            }}
          >
            <label>
              Catalog
              <select
                value={group}
                onChange={(event) => {
                  setGroup(event.target.value as Group);
                  setNoradId(undefined);
                  setIdInput("");
                  setSelectedId(undefined);
                }}
              >
                <option value="stations">Space stations</option>
                <option value="starlink">Starlink</option>
                <option value="active">Active satellites</option>
                <option value="weather">Weather satellites</option>
                <option value="gps-ops">GPS operational</option>
              </select>
            </label>
            <label>
              NORAD ID
              <input
                type="number"
                min="1"
                max="999999999"
                step="1"
                placeholder="e.g. 25544"
                value={idInput}
                onChange={(event) => setIdInput(event.target.value)}
              />
            </label>
            <button type="submit">
              {idInput.trim() ? "Find satellite" : "Show catalog"}
            </button>
            <span className="map-hint">
              Up to 100 objects · click a satellite to inspect
            </span>
          </form>
        )}
        <div className="view-notice">
          {mode === "live"
            ? "Calculated positions from CelesTrak orbital elements. These are predictions, not onboard GPS telemetry."
            : "Synthetic demonstration · accelerated 120× · not real satellite positions."}
        </div>
        {scene.isPending && (
          <p className="notice" role="status">
            Loading orbital data…
          </p>
        )}
        {scene.error && (
          <p className="notice error" role="alert">
            {scene.error.message}{" "}
            <button onClick={() => scene.refetch()}>Retry local view</button>
          </p>
        )}
        {expired && (
          <p className="notice error" role="alert">
            Position window expired. Live markers are hidden until a fresh
            propagation is available.
          </p>
        )}
        {scene.data?.warnings.map((w) => (
          <p className="notice" key={w}>
            {w}
          </p>
        ))}
        <div className="orbital-workspace">
          <div className="globe-wrap">
            <SpaceGlobe
              scene={scene.data}
              selectedId={selected?.satellite_id}
              onSelect={setSelectedId}
              groundTrack={mode === "live" ? track.data : undefined}
            />
            <div className="legend">
              <span className="sun-dot" />
              Sunlit <span className="eclipse-dot" />
              Eclipse <span className="ground-line" />
              Selected ground track
            </div>
          </div>
          <aside className="inspector" aria-label="Satellite details">
            <p className="eyebrow">
              {mode === "live" ? "SATELLITE INSPECTOR" : "DEMONSTRATION"}
            </p>
            <label className="satellite-choice">
              Satellite
              <select
                value={selected?.satellite_id ?? ""}
                onChange={(e) => setSelectedId(e.target.value)}
                disabled={!scene.data?.tracks.length}
              >
                {!scene.data?.tracks.length && (
                  <option value="">No satellite available</option>
                )}
                {scene.data?.tracks.map((t) => (
                  <option key={t.satellite_id} value={t.satellite_id}>
                    {t.name}
                    {t.norad_id ? ` · ${t.norad_id}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <h2>{selected?.name ?? "Waiting for data"}</h2>
            <span className={`badge ${selected?.stale ? "warning" : ""}`}>
              {mode === "demo"
                ? "Synthetic"
                : expired
                  ? "Window expired"
                  : illuminationLabel(sample?.illumination_fraction)}
            </span>
            <div className="kpis">
              <div>
                <span>Altitude</span>
                <strong>
                  {sample ? (sample.altitude_m / 1000).toFixed(1) : "—"}
                  <small> km</small>
                </strong>
              </div>
              <div>
                <span>Inertial speed</span>
                <strong>
                  {sample?.speed_m_s != null
                    ? (sample.speed_m_s / 1000).toFixed(2)
                    : "—"}
                  <small> km/s</small>
                </strong>
              </div>
              <div>
                <span>Latitude</span>
                <strong>
                  {sample ? sample.latitude_deg.toFixed(3) : "—"}
                  <small>°</small>
                </strong>
              </div>
              <div>
                <span>Longitude</span>
                <strong>
                  {sample ? sample.longitude_deg.toFixed(3) : "—"}
                  <small>°</small>
                </strong>
              </div>
            </div>
            <dl className="provenance">
              <dt>Source</dt>
              <dd>{selected?.source ?? "Unavailable"}</dd>
              <dt>Orbit epoch</dt>
              <dd>{timestamp(selected?.element_epoch)}</dd>
              <dt>Element age</dt>
              <dd>
                {ageHours === null
                  ? "Unavailable"
                  : `${Math.abs(ageHours).toFixed(1)} h ${ageHours < 0 ? "ahead of now" : "old"}`}
                {selected?.stale && <b className="old-data"> · stale data</b>}
              </dd>
              <dt>Downloaded</dt>
              <dd>{timestamp(selected?.retrieved_at)}</dd>
              <dt>Calculated</dt>
              <dd>{timestamp(scene.data?.generated_at)}</dd>
            </dl>
            {track.error && mode === "live" && (
              <p className="notice error">
                Ground track: {track.error.message}
              </p>
            )}
            {mode === "live" && (
              <p className="detail-note">
                WGS84 altitude · GCRS velocity. Display interpolates 5-second
                samples at current time. Ground track spans −45 to +90 minutes.
                Eclipse estimates exclude atmosphere and Earth oblateness.
              </p>
            )}
            {selected?.source_sha256 && (
              <details>
                <summary>Snapshot checksum</summary>
                <code>{selected.source_sha256}</code>
              </details>
            )}
          </aside>
        </div>
        <footer className="view-footer">
          <span>
            {scene.data?.tracks.length ?? 0} displayed /{" "}
            {scene.data?.catalog_count ?? 0} catalog objects
          </span>
          <span>Elements cached ≥2 hours · local scene refresh 60 seconds</span>
        </footer>
      </section>
      <p className="footnote">
        Position estimates degrade as elements age, particularly after
        manoeuvres. Orbit geometry alone does not determine PV output; attitude,
        array design and telemetry are also needed.{" "}
        <a
          href="https://celestrak.org/NORAD/documentation/gp-data-formats.php"
          target="_blank"
          rel="noreferrer"
        >
          Orbital data: CelesTrak
        </a>
      </p>
    </main>
  );
}
