import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

const cesiumSource = "node_modules/cesium/Build/Cesium";
const cesiumBaseUrl = "cesiumStatic";

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: `${cesiumSource}/ThirdParty`,
          dest: cesiumBaseUrl,
          rename: { stripBase: 4 },
        },
        {
          src: `${cesiumSource}/Workers`,
          dest: cesiumBaseUrl,
          rename: { stripBase: 4 },
        },
        {
          src: `${cesiumSource}/Assets`,
          dest: cesiumBaseUrl,
          rename: { stripBase: 4 },
        },
        {
          src: `${cesiumSource}/Widgets`,
          dest: cesiumBaseUrl,
          rename: { stripBase: 4 },
        },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify(cesiumBaseUrl),
  },
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.SPACE_PV_API_PROXY ?? "http://localhost:8000",
      "/health": process.env.SPACE_PV_API_PROXY ?? "http://localhost:8000",
    },
  },
});
