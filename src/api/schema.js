import { z } from "zod";

const sceneSchema = z.object({
  scene_id: z.string(),
  date: z.string(),
  cloud: z.number(),
  tier: z.string(),
  season: z.string(),
  aoi: z.string(),
  aoi_label: z.string(),
  overlap_pct: z.number().optional(),
});

const metricsSchema = z.object({
  scenes_discovered: z.number(),
  scenes_retained_default: z.number().optional(),
  water_area_wet_km2: z.number(),
  water_area_dry_km2: z.number(),
  model: z.object({
    accuracy: z.number(),
    weighted_f1: z.number(),
    macro_f1: z.number(),
    test_samples: z.number(),
  }),
  generated_at: z.string().optional(),
});

const geoJsonSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(z.record(z.unknown())),
});

export function validateScenes(data) {
  return z.array(sceneSchema).parse(data);
}

export function validateMetrics(data) {
  return metricsSchema.parse(data);
}

export function validateGeoJson(data) {
  return geoJsonSchema.parse(data);
}
