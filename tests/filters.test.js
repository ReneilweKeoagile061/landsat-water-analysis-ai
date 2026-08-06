import { describe, expect, it } from "vitest";
import { filterPoints, filterScenes } from "../src/state/filters.js";
import { minMax, normalize, sampleArray } from "../src/utils/geo.js";

const sampleScenes = [
  { scene_id: "a", cloud: 5, tier: "Tier 1", season: "Wet Season", aoi: "OKAVANGO" },
  { scene_id: "b", cloud: 25, tier: "Tier 1", season: "Dry Season", aoi: "KALAHARI" },
  { scene_id: "c", cloud: 8, tier: "Tier 2", season: "Wet Season", aoi: "OKAVANGO" },
];

const samplePoints = [
  { properties: { aoi: "OKAVANGO", season: "Wet Season", tier: "Tier 1" } },
  { properties: { aoi: "KALAHARI", season: "Dry Season", tier: "Tier 1" } },
];

describe("filterScenes", () => {
  it("filters by cloud, tier, season, and aoi", () => {
    const result = filterScenes(sampleScenes, {
      cloud: 20,
      tier: "Tier 1",
      season: "Wet Season",
      aoi: "OKAVANGO",
    });
    expect(result).toHaveLength(1);
    expect(result[0].scene_id).toBe("a");
  });
});

describe("filterPoints", () => {
  it("applies the same constraints to map points", () => {
    const result = filterPoints(samplePoints, {
      cloud: 20,
      tier: "Tier 1",
      season: "Wet Season",
      aoi: "ALL",
    });
    expect(result).toHaveLength(1);
  });
});

describe("geo helpers", () => {
  it("normalizes values within range", () => {
    expect(normalize(5, 0, 10)).toBe(0.5);
  });

  it("computes min and max safely", () => {
    expect(minMax([2, 8, 4])).toEqual({ min: 2, max: 8 });
  });

  it("samples large arrays down", () => {
    const input = Array.from({ length: 100 }, (_, index) => index);
    expect(sampleArray(input, 10)).toHaveLength(10);
  });
});
