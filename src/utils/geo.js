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
