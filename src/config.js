export const DATA_BASE = import.meta.env.VITE_DATA_BASE_URL || "/data/exports";

export const AOI_LABELS = {
  OKAVANGO: "Okavango Delta",
  KALAHARI: "Kalahari Fringe",
  TRANSITIONAL: "Transitional Zone",
};

export const HEATMAP_MAX_POINTS = 1200;
export const HEATMAP_OFFSETS = [
  [0.04, 0.03],
  [-0.03, 0.04],
  [0.02, -0.04],
];

export const DEFAULT_FILTERS = {
  aoi: "ALL",
  cloud: 20,
  season: "Wet Season",
  tier: "Tier 1",
};
