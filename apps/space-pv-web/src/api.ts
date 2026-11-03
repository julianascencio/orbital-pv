export type Health = { status: string; service: string };
export type Group = "stations" | "starlink" | "active" | "weather" | "gps-ops";
export type OrbitSample = {
  timestamp: string;
  longitude_deg: number;
  latitude_deg: number;
  altitude_m: number;
  speed_m_s?: number | null;
  velocity_gcrs_m_s?: [number, number, number] | null;
  illumination_fraction?: number | null;
};
export type MapTrack = {
  satellite_id: string;
  name: string;
  source: string;
  samples: OrbitSample[];
  norad_id?: number | null;
  element_epoch?: string | null;
  retrieved_at?: string | null;
  element_age_s?: number | null;
  source_sha256?: string | null;
  stale?: boolean;
  position_kind?: string;
};
export type MapScene = {
  generated_at: string;
  mode: "live" | "demo";
  tracks: MapTrack[];
  warnings: string[];
  catalog_count: number;
  omitted_count: number;
  sample_interval_s: number;
};
async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export const getHealth = () => get<Health>("/health");
export const getDemoMapScene = () => get<MapScene>("/api/v1/map/demo");
export function getLiveMapScene(group: Group, noradId?: number) {
  const query = new URLSearchParams({ group });
  if (noradId) query.set("norad_id", String(noradId));
  return get<MapScene>(`/api/v1/map/live?${query}`);
}
export function getLiveTrack(id: string, group: Group, individual: boolean) {
  return get<MapTrack>(
    `/api/v1/map/live/${encodeURIComponent(id)}/track?${new URLSearchParams({ group, individual: String(individual) })}`,
  );
}
