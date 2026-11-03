import test from "node:test";
import assert from "node:assert/strict";
import {
  sampleAt,
  splitGroundTrack,
  illuminationLabel,
} from "../src/tracking.ts";
const start = Date.parse("2026-11-02T00:00:00Z");
const points = [
  {
    timestamp: new Date(start).toISOString(),
    longitude_deg: 179,
    latitude_deg: 1,
    altitude_m: 400000,
    speed_m_s: 7500,
    illumination_fraction: 1,
  },
  {
    timestamp: new Date(start + 5000).toISOString(),
    longitude_deg: -179,
    latitude_deg: 3,
    altitude_m: 402000,
    speed_m_s: 7600,
    illumination_fraction: 0,
  },
];
test("interpolates around the date line, never through Greenwich", () => {
  const sample = sampleAt(points, start + 2500);
  assert.equal(Math.abs(sample.longitude_deg), 180);
  assert.equal(sample.latitude_deg, 2);
  assert.equal(sample.altitude_m, 401000);
  assert.equal(sample.speed_m_s, 7550);
});
test("expired windows and empty states never become current positions", () => {
  assert.equal(sampleAt(points, start - 1), undefined);
  assert.equal(sampleAt(points, start + 5001), undefined);
  assert.equal(sampleAt([], start), undefined);
  assert.equal(sampleAt([points[0]], start).longitude_deg, 179);
});
test("keeps ground segments on their own side of the date line", () => {
  const samples = [-170, -179, 179, 170].map((longitude_deg) => ({
    ...points[0],
    longitude_deg,
  }));
  assert.deepEqual(
    splitGroundTrack(samples).map((part) => part.map((s) => s.longitude_deg)),
    [
      [-170, -179],
      [179, 170],
    ],
  );
});
test("illumination distinguishes unknown, penumbra and eclipse", () => {
  assert.equal(illuminationLabel(null), "Unknown");
  assert.equal(illuminationLabel(0), "Eclipse");
  assert.equal(illuminationLabel(0.5), "Penumbra");
  assert.equal(illuminationLabel(1), "Sunlit");
});
