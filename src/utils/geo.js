export function debounce(fn, wait = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function minMax(values) {
  if (!values.length) return { min: 0, max: 1 };
  let min = values[0];
  let max = values[0];
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return { min, max };
}

export function sampleArray(items, maxItems) {
  if (items.length <= maxItems) return items;
  const step = items.length / maxItems;
  const sampled = [];
  for (let i = 0; i < maxItems; i += 1) {
    sampled.push(items[Math.floor(i * step)]);
  }
  return sampled;
}

export function normalize(value, min, max) {
  if (max === min) return 0.5;
  return Math.max(0.05, Math.min(1, (value - min) / (max - min)));
}

export function scoreToColor(score) {
  if (score >= 0.7) return { fill: "#f5c84c", stroke: "#e8a820" };
  if (score >= 0.45) return { fill: "#4db4ff", stroke: "#2a8fd4" };
  return { fill: "#8ed8ff", stroke: "#5eb8e8" };
}

export function getBbox(ring) {
  const lons = ring.map((coord) => coord[0]);
  const lats = ring.map((coord) => coord[1]);
  return {
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

export function softEllipseFromRing(ring, segments = 48) {
  const bbox = getBbox(ring);
  const cx = (bbox.minLon + bbox.maxLon) / 2;
  const cy = (bbox.minLat + bbox.maxLat) / 2;
  const rx = (bbox.maxLon - bbox.minLon) / 2 + 0.08;
  const ry = (bbox.maxLat - bbox.minLat) / 2 + 0.08;
  const coords = [];

  for (let i = 0; i <= segments; i += 1) {
    const angle = (i / segments) * Math.PI * 2;
    coords.push([cx + rx * Math.cos(angle), cy + ry * Math.sin(angle)]);
  }
  return coords;
}

export function computeAoiScores(points) {
  const grouped = {};
  points.forEach((feature) => {
    const key = feature.properties.aoi;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(Number(feature.properties.high_prob || 0));
  });

  const scores = {};
  Object.entries(grouped).forEach(([aoi, values]) => {
    scores[aoi] = values.reduce((sum, value) => sum + value, 0) / values.length;
  });
  return scores;
}

export function pointInPolygon(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];

    const intersect = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function polygonAreaHectares(ring) {
  if (!ring || ring.length < 3) return 0;
  // Spherical approximation for area in m2, then convert to ha
  const DEG_TO_RAD = Math.PI / 180;
  const R = 6378137; // Earth radius in meters
  let area = 0;

  for (let i = 0; i < ring.length; i += 1) {
    const j = (i + 1) % ring.length;
    const p1 = ring[i];
    const p2 = ring[j];
    area += (p2[0] - p1[0]) * DEG_TO_RAD * (2 + Math.sin(p1[1] * DEG_TO_RAD) + Math.sin(p2[1] * DEG_TO_RAD));
  }
  area = (Math.abs(area) * R * R) / 2.0;
  return Math.round((area / 10000) * 10) / 10;
}

export function analyzePolygonWaterPotential(ring, points) {
  const insidePoints = points.filter((feature) => {
    const [lon, lat] = feature.geometry.coordinates;
    return pointInPolygon(lon, lat, ring);
  });

  const total = insidePoints.length;
  const hectares = polygonAreaHectares(ring);

  if (total === 0) {
    return {
      hectares,
      sampleCount: 0,
      shares: { Low: 50, Medium: 30, High: 20 },
      insidePoints: [],
    };
  }

  let lowCount = 0;
  let medCount = 0;
  let highCount = 0;
  let sumDtwt = 0;
  let sumProductivity = 0;
  let sumBoreholeScore = 0;
  let sumClay = 0;
  let sumInfiltration = 0;
  const dtwtClasses = {};
  let bestPoint = null;
  let bestScore = -1;

  insidePoints.forEach((feature) => {
    const props = feature.properties;
    const label = props.predicted_label;
    if (label === "High") highCount += 1;
    else if (label === "Medium") medCount += 1;
    else lowCount += 1;

    const dtwt = Number(props.depth_to_water_table_m || 45);
    const prod = Number(props.aquifer_productivity_ls || 2.5);
    const bScore = Number(props.borehole_feasibility_score || 0.65);
    const clay = Number(props.clay_fraction_pct || 20);
    const infiltration = Number(props.infiltration_score ?? 100 - clay);
    const dtwtClass = props.dtwt_class || (dtwt < 25 ? "Shallow (<25 m)" : dtwt <= 75 ? "Moderate (25-75 m)" : "Deep (>75 m)");

    sumDtwt += dtwt;
    sumProductivity += prod;
    sumBoreholeScore += bScore;
    sumClay += clay;
    sumInfiltration += infiltration;
    dtwtClasses[dtwtClass] = (dtwtClasses[dtwtClass] || 0) + 1;

    if (bScore > bestScore) {
      bestScore = bScore;
      bestPoint = feature;
    }
  });

  const shareLow = Math.round((lowCount / total) * 100);
  const shareMed = Math.round((medCount / total) * 100);
  const shareHigh = total > 0 ? Math.round((highCount / total) * 100) : 0;

  return {
    hectares,
    sampleCount: total,
    shares: { Low: shareLow, Medium: shareMed, High: shareHigh },
    insidePoints,
    avgDtwt: Math.round((sumDtwt / total) * 10) / 10,
    avgProductivity: Math.round((sumProductivity / total) * 10) / 10,
    avgBoreholeScore: Math.round((sumBoreholeScore / total) * 100),
    avgClay: Math.round(sumClay / total),
    avgInfiltration: Math.round(sumInfiltration / total),
    dtwtClass: Object.entries(dtwtClasses).sort((left, right) => right[1] - left[1])[0][0],
    bestBoreholePoint: bestPoint,
    recommendedAction: bestPoint?.properties?.recommended_action || "Targeted Borehole Siting",
    aquiferType: bestPoint?.properties?.aquifer_type || "Fractured Karoo / Alluvial Sandstone",
  };
}


