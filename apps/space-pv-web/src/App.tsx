import { useQuery } from "@tanstack/react-query";
import { getDemoMapScene, getHealth } from "./api";
import { SpaceGlobe } from "./components/SpaceGlobe";

const modules = [
  ["Satellites", "Catalog, mission metadata and orbital state"],
  ["Orbit", "Propagation, Sun geometry, eclipse and attitude"],
  ["PV Performance", "Expected vs measured power and I-V models"],
  ["Telemetry", "EPS, thermal, ADCS and environment signals"],
  ["Jobs", "Ingestion and analytics execution history"],
  ["Labs", "Reproducible scientific experiments and benchmarks"],
];

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });
  const mapScene = useQuery({ queryKey: ["map-demo"], queryFn: getDemoMapScene, retry: false });

  return (
    <main className="shell">
      <header className="hero compact">
        <p className="eyebrow">SPACE PV ANALYTICS</p>
        <h1>Orbital PV intelligence.</h1>
        <p className="lede">
          Space-time GIS, orbit-aware PV modelling, real flight telemetry and degradation analytics.
        </p>
        <div className="status">
          <span className={health.data?.status === "ok" ? "dot online" : "dot"} />
          API {health.data?.status === "ok" ? "connected" : "offline"}
        </div>
      </header>

      <section className="map-panel">
        <div className="map-panel-head">
          <div>
            <p className="eyebrow">SPACE GIS</p>
            <h2>Dynamic orbital view</h2>
          </div>
          <span className="map-hint">Drag Earth · scroll to zoom · use timeline to scrub time</span>
        </div>
        <SpaceGlobe scene={mapScene.data} />
      </section>

      <section className="grid">
        {modules.map(([title, text]) => (
          <article className="card" key={title}>
            <h2>{title}</h2>
            <p>{text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
