import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

// A successful JS bundle is insufficient: Cesium fetches these by runtime URLs.
const base = resolve("dist/cesiumStatic");
const terrain = JSON.parse(
  await readFile(`${base}/Assets/approximateTerrainHeights.json`, "utf8"),
);
assert.ok(Object.keys(terrain).length);
assert.match(
  await readFile(
    `${base}/Assets/Textures/NaturalEarthII/tilemapresource.xml`,
    "utf8",
  ),
  /TileMap/,
);
const sky = await readFile(`${base}/Assets/Textures/SkyBox/tycho2t3_80_px.jpg`);
assert.equal(sky[0], 0xff);
assert.equal(sky[1], 0xd8);
assert.ok(
  (await readFile(`${base}/Workers/createVerticesFromHeightmap.js`)).length >
    100,
);
console.log("Cesium runtime assets verified at the URLs used by the globe.");
