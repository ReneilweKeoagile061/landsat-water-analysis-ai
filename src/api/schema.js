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
    spatial_cv: z
      .object({
        blocks: z.array(z.number()),
        mean: z.number(),
      })
      .optional(),
    label_agreement: z
      .object({
        rule_based_vs_kmeans: z.number(),
        chance_baseline: z.number(),
      })
      .optional(),
    per_class: z
      .object({
        low: z.object({ f1: z.number() }),
        medium: z.object({ f1: z.number() }),
        high: z.object({ f1: z.number() }),
      })
      .optional(),
  }),
  generated_at: z.string().optional(),
});

const pointGeometrySchema = z.object({
  type: z.literal("Point"),
  coordinates: z.tuple([z.number(), z.number()]),
});

const polygonGeometrySchema = z.object({
  type: z.literal("Polygon"),
  coordinates: z.array(z.array(z.tuple([z.number(), z.number()]))),
});

const waterPointPropsSchema = z.object({
  aoi: z.string(),
  scene_id: z.string().optional(),
  season: z.string(),
  tier: z.string(),
  ndwi: z.number(),
  mndwi: z.number(),
  high_prob: z.number(),
  predicted_label: z.enum(["Low", "Medium", "High"]),
  elevation: z.number().optional(),
  slope: z.number().optional(),
  depth_to_water_table_m: z.number().optional(),
  dtwt_class: z.string().optional(),
  aquifer_productivity_ls: z.number().optional(),
  aquifer_type: z.string().optional(),
  clay_fraction_pct: z.number().optional(),
  clay_0_5_pct: z.number().optional(),
  clay_15_30_pct: z.number().optional(),
  clay_60_100_pct: z.number().optional(),
  clay_100_200_pct: z.number().optional(),
  phreatophyte_activity: z.number().optional(),
  phreatophyte_index: z.number().optional(),
  phreatophyte_method: z.string().optional(),
  infiltration_score: z.number().optional(),
  infiltration_class: z.string().optional(),
  evidence_confidence: z.number().optional(),
  drill_depth_min_m: z.number().optional(),
  drill_depth_max_m: z.number().optional(),
  validation_next_step: z.string().optional(),
  subsurface_data_source: z.string().optional(),
  subsurface_data_quality: z.string().optional(),
  soilgrids_query_date: z.string().optional(),
  borehole_feasibility_score: z.number().optional(),
  recommended_action: z.string().optional(),
});

const aoiPropsSchema = z.object({
  aoi: z.string(),
  color: z.string().optional(),
});

const waterPointsSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: pointGeometrySchema,
      properties: waterPointPropsSchema,
    })
  ),
});

const aoisSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: polygonGeometrySchema,
      properties: aoiPropsSchema,
    })
  ),
});

export function validateScenes(data) {
  return z.array(sceneSchema).parse(data);
}

export function validateMetrics(data) {
  return metricsSchema.parse(data);
}

export function validateWaterPoints(data) {
  return waterPointsSchema.parse(data);
}

export function validateAois(data) {
  return aoisSchema.parse(data);
}
