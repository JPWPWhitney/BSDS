import { defineConfig } from "vite";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { resolve } from "node:path";

const cesiumSource = "node_modules/cesium/Build/Cesium";

export default defineConfig({
  base: "./",
  define: {
    CESIUM_BASE_URL: JSON.stringify("./cesium"),
  },
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        player: resolve(__dirname, "player.html"),
        lab: resolve(__dirname, "lab.html"),
      },
    },
  },
  plugins: [
    viteStaticCopy({
      targets: [
        { src: `${cesiumSource}/Workers`, dest: "cesium" },
        { src: `${cesiumSource}/ThirdParty`, dest: "cesium" },
        { src: `${cesiumSource}/Assets`, dest: "cesium" },
        { src: `${cesiumSource}/Widgets`, dest: "cesium" },
      ],
    }),
  ],
});
