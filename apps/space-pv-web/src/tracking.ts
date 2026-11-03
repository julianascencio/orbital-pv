import type { OrbitSample } from "./api";

/** Display interpolation only; never extrapolate outside the propagated window. */
export function sampleAt(
  samples: OrbitSample[],
  timeMs: number,
): OrbitSample | undefined {
  if (
    !samples.length ||
    timeMs < Date.parse(samples[0].timestamp) ||
    timeMs > Date.parse(samples[samples.length - 1].timestamp)
  )
    return undefined;
  let lo = 0;
  let hi = samples.length - 1;
  while (lo + 1 < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (Date.parse(samples[mid].timestamp) <= timeMs) lo = mid;
    else hi = mid;
  }
  const a = samples[lo];
  const b = samples[hi];
  const width = Date.parse(b.timestamp) - Date.parse(a.timestamp);
  const ratio = width > 0 ? (timeMs - Date.parse(a.timestamp)) / width : 0;
  const lerp = (x: number, y: number) => x + (y - x) * ratio;
  const deltaLon = ((b.longitude_deg - a.longitude_deg + 540) % 360) - 180;
  return {
    timestamp: new Date(timeMs).toISOString(),
    longitude_deg: ((a.longitude_deg + deltaLon * ratio + 540) % 360) - 180,
    latitude_deg: lerp(a.latitude_deg, b.latitude_deg),
    altitude_m: lerp(a.altitude_m, b.altitude_m),
    speed_m_s:
      a.speed_m_s != null && b.speed_m_s != null
        ? lerp(a.speed_m_s, b.speed_m_s)
        : null,
    illumination_fraction: (ratio < 0.5 ? a : b).illumination_fraction,
  };
}
/** Break ground lines at the date line instead of drawing across the world. */
export function splitGroundTrack(samples: OrbitSample[]): OrbitSample[][] {
  const parts: OrbitSample[][] = [[]];
  for (const sample of samples) {
    const part = parts[parts.length - 1];
    if (
      part.length &&
      Math.abs(sample.longitude_deg - part[part.length - 1].longitude_deg) > 180
    )
      parts.push([]);
    parts[parts.length - 1].push(sample);
  }
  return parts.filter((part) => part.length > 1);
}
export function illuminationLabel(value?: number | null): string {
  if (value == null) return "Unknown";
  return value <= 0.001 ? "Eclipse" : value >= 0.999 ? "Sunlit" : "Penumbra";
}
