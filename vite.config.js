import { defineConfig } from "vite";

export default defineConfig({
  base: "/",
  publicDir: "public",
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          leaflet: ["leaflet", "leaflet.heat", "leaflet.markercluster"],
        },
      },
    },
  },
  test: {
    environment: "node",
  },
});
