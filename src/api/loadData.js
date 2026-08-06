import { DATA_BASE } from "../config.js";
import { validateGeoJson, validateMetrics, validateScenes } from "./schema.js";

const LOADERS = {
  aois: { path: "aois.geojson", validate: validateGeoJson },
  waterPoints: { path: "water_points.geojson", validate: validateGeoJson },
  scenes: { path: "scenes.json", validate: validateScenes },
  metrics: { path: "metrics.json", validate: validateMetrics },
};

async function loadResource(name, retries = 2) {
  const config = LOADERS[name];
  const url = `${DATA_BASE}/${config.path}`;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, { cache: "no-cache" });
      if (!response.ok) {
        throw new Error(`${config.path} returned ${response.status}`);
      }
      const json = await response.json();
      return { name, data: config.validate(json), error: null };
    } catch (error) {
      if (attempt === retries) {
        return { name, data: null, error: error.message };
      }
      await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)));
    }
  }

  return { name, data: null, error: "Unknown load failure" };
}

export async function loadData(onProgress) {
  const names = Object.keys(LOADERS);
  const results = {};
  const errors = {};

  await Promise.all(
    names.map(async (name) => {
      onProgress?.(name, "loading");
      const result = await loadResource(name);
      if (result.error) {
        errors[name] = result.error;
        onProgress?.(name, "error");
      } else {
        results[name] = result.data;
        onProgress?.(name, "ready");
      }
    })
  );

  return {
    aois: results.aois ?? null,
    waterPoints: results.waterPoints ?? null,
    scenes: results.scenes ?? [],
    metrics: results.metrics ?? null,
    errors,
    isReady: Boolean(results.aois && results.waterPoints && results.metrics),
  };
}
