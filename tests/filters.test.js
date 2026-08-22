import { describe, expect, it } from "vitest";
import { filterPoints, filterScenes } from "../src/state/filters.js";
import { estimateWaterGain } from "../src/ui/dashboard.js";
import {
  analyzePolygonWaterPotential,
  minMax,
  normalize,
  pointInPolygon,
  polygonAreaHectares,
  sampleArray,
} from "../src/utils/geo.js";

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
      minPotential: 0,
    });
    expect(result).toHaveLength(1);
  });

  it("filters points below the minPotential confidence threshold", () => {
    const potentialPoints = [
      { properties: { aoi: "OKAVANGO", season: "Wet Season", tier: "Tier 1", high_prob: 0.95 } },
      { properties: { aoi: "OKAVANGO", season: "Wet Season", tier: "Tier 1", high_prob: 0.82 } },
      { properties: { aoi: "OKAVANGO", season: "Wet Season", tier: "Tier 1", high_prob: 0.45 } },
    ];
    const primeResults = filterPoints(potentialPoints, {
      cloud: 20,
      tier: "Tier 1",
      season: "Wet Season",
      aoi: "ALL",
      minPotential: 0.9,
    });
    expect(primeResults).toHaveLength(1);
    expect(primeResults[0].properties.high_prob).toBe(0.95);
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

describe("water gain calculator", () => {
  it("matches the 50 ha / 450 mm case study", () => {
    const result = estimateWaterGain({
      hectares: 50,
      rainfallMm: 450,
      shares: { Low: 50, Medium: 30, High: 20 },
    });
    expect(result.landingM3).toBe(225000);
    expect(result.zones[0].m3).toBe(11250);
    expect(result.zones[1].m3).toBe(23625);
    expect(result.zones[2].m3).toBe(29250);
    expect(result.totalM3).toBe(64125);
  });
});

describe("property polygon analysis", () => {
  const squareRing = [
    [22.0, -19.0],
    [23.0, -19.0],
    [23.0, -20.0],
    [22.0, -20.0],
    [22.0, -19.0],
  ];

  it("calculates polygon area in hectares", () => {
    const area = polygonAreaHectares(squareRing);
    expect(area).toBeGreaterThan(100000);
  });

  it("tests point in polygon containment", () => {
    expect(pointInPolygon(22.5, -19.5, squareRing)).toBe(true);
    expect(pointInPolygon(24.0, -19.5, squareRing)).toBe(false);
  });

  it("analyzes water potential for points inside a property polygon", () => {
    const testPoints = [
      { geometry: { coordinates: [22.5, -19.5] }, properties: { predicted_label: "High" } },
      { geometry: { coordinates: [22.6, -19.6] }, properties: { predicted_label: "High" } },
      { geometry: { coordinates: [22.4, -19.4] }, properties: { predicted_label: "Medium" } },
      { geometry: { coordinates: [22.3, -19.3] }, properties: { predicted_label: "Low" } },
      { geometry: { coordinates: [25.0, -21.0] }, properties: { predicted_label: "Low" } }, // outside
    ];

    const result = analyzePolygonWaterPotential(squareRing, testPoints);
    expect(result.sampleCount).toBe(4);
    expect(result.shares.High).toBe(50);
    expect(result.shares.Medium).toBe(25);
    expect(result.shares.Low).toBe(25);
  });
});


