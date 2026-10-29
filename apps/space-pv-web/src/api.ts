export type Health = { status: string; service: string };

export type OrbitSample = {
  timestamp: string;
  longitude_deg: number;
  latitude_deg: number;
  altitude_m: number;
};

export type MapTrack = {
  satellite_id: string;
  name: string;
  source: string;
  samples: OrbitSample[];
};

export type MapScene = {
  generated_at: string;
  tracks: MapTrack[];
};

export async function getHealth(): Promise<Health> {
  const response = await fetch("/health");
  if (!response.ok) throw new Error("API health request failed");
  return response.json() as Promise<Health>;
}

export async function getDemoMapScene(): Promise<MapScene> {
  const response = await fetch("/api/v1/map/demo");
  if (!response.ok) throw new Error("Map scene request failed");
  return response.json() as Promise<MapScene>;
}
