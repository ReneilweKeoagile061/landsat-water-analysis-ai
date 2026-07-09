const DATA_BASE = "./data/exports";

const sceneTableBody = document.getElementById("sceneTableBody");
const runBtn = document.getElementById("runBtn");
const aoiStats = document.getElementById("aoiStats");
const modelMetricsList = document.getElementById("modelMetricsList");
const aoiInput = document.getElementById("aoiInput");
const cloudInput = document.getElementById("cloudInput");
const cloudValue = document.getElementById("cloudValue");
const toggleNdwi = document.getElementById("toggleNdwi");
const toggleMndwi = document.getElementById("toggleMndwi");
const toggleRegions = document.getElementById("toggleRegions");
const toggleClasses = document.getElementById("toggleClasses");
const mapTooltip = document.getElementById("mapTooltip");

const AOI_LABELS = {
  OKAVANGO: "Okavango Delta",
  KALAHARI: "Kalahari Fringe",
  TRANSITIONAL: "Transitional Zone",
};

const map = L.map("waterMap", {
  zoomControl: false,
  scrollWheelZoom: true,
  zoomSnap: 0.25,
  zoomDelta: 0.5,
  wheelDebounceTime: 35,
  wheelPxPerZoomLevel: 90,
  preferCanvas: true,
  inertia: true,
  inertiaDeceleration: 2800,
  easeLinearity: 0.22,
}).setView([-20.6, 24.5], 6.5);

L.control.zoom({ position: "bottomright" }).addTo(map);

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap &copy; CARTO",
}).addTo(map);

let appData = null;
let regionLayer = null;
let classLayer = null;
let ndwiLayer = null;
let mndwiLayer = null;
let aoiScores = {};

function normalize(value, min, max) {
  if (max === min) return 0.5;
  return Math.max(0.05, Math.min(1, (value - min) / (max - min)));
}

function scoreToColor(score) {
  if (score >= 0.7) return { fill: "#f5c84c", stroke: "#e8a820" };
  if (score >= 0.45) return { fill: "#4db4ff", stroke: "#2a8fd4" };
  return { fill: "#8ed8ff", stroke: "#5eb8e8" };
}

function getBbox(ring) {
  const lons = ring.map((c) => c[0]);
  const lats = ring.map((c) => c[1]);
  return {
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

function softEllipseFromRing(ring, segments = 48) {
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

function computeAoiScores(points) {
  const grouped = {};
  points.forEach((feature) => {
    const key = feature.properties.aoi;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(Number(feature.properties.high_prob || 0));
  });

  const scores = {};
  Object.entries(grouped).forEach(([aoi, values]) => {
    scores[aoi] = values.reduce((sum, v) => sum + v, 0) / values.length;
  });
  return scores;
}

function buildHeatPayload(points, key) {
  const values = points.map((f) => Number(f.properties[key]));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const payload = [];

  points.forEach((feature, index) => {
    const [lon, lat] = feature.geometry.coordinates;
    const base = normalize(Number(feature.properties[key]), min, max);
    payload.push([lat, lon, base]);

    const offsets = [
      [0.04, 0.03],
      [-0.03, 0.04],
      [0.02, -0.04],
      [-0.04, -0.02],
      [0.05, 0.0],
    ];
    offsets.forEach(([dLat, dLon], i) => {
      payload.push([lat + dLat, lon + dLon, base * (0.72 - i * 0.06)]);
    });
  });

  return payload;
}

function showTooltip(html, x, y) {
  mapTooltip.innerHTML = html;
  mapTooltip.hidden = false;
  mapTooltip.style.left = `${x}px`;
  mapTooltip.style.top = `${y}px`;
}

function hideTooltip() {
  mapTooltip.hidden = true;
}

function bindRegionHover(feature, layer) {
  const baseStyle = () => {
    const score = feature.properties.score;
    const colors = scoreToColor(score);
    return {
      color: colors.stroke,
      weight: 1.5,
      opacity: 0.55,
      fillColor: colors.fill,
      fillOpacity: 0.28 + score * 0.18,
    };
  };

  layer.on("mouseover", (event) => {
    const container = map.getContainer().getBoundingClientRect();
    const x = event.originalEvent.clientX - container.left;
    const y = event.originalEvent.clientY - container.top;
    const { aoi, score, pointCount } = feature.properties;
    showTooltip(regionTooltip(aoi, score, pointCount), x, y);
    layer.setStyle({ fillOpacity: 0.52, weight: 2.5, opacity: 0.85 });
  });

  layer.on("mousemove", (event) => {
    const container = map.getContainer().getBoundingClientRect();
    mapTooltip.style.left = `${event.originalEvent.clientX - container.left}px`;
    mapTooltip.style.top = `${event.originalEvent.clientY - container.top}px`;
  });

  layer.on("mouseout", () => {
    hideTooltip();
    layer.setStyle(baseStyle());
  });
}

function regionTooltip(aoi, score, pointCount) {
  const label = AOI_LABELS[aoi] || aoi;
  const badge =
    score >= 0.7 ? "high" : score >= 0.45 ? "medium" : "low";
  const potential = badge.charAt(0).toUpperCase() + badge.slice(1);
  return `
    <h4>${label}</h4>
    <p>Avg high-water probability: <strong>${(score * 100).toFixed(1)}%</strong></p>
    <p>Sample points: ${pointCount}</p>
    <span class="tooltip-badge ${badge}">${potential} potential region</span>
  `;
}

function pointTooltip(props) {
  const badge = props.predicted_label.toLowerCase();
  return `
    <h4>${AOI_LABELS[props.aoi] || props.aoi}</h4>
    <p>Scene: ${props.scene_id || "N/A"}</p>
    <p>NDWI: <strong>${Number(props.ndwi).toFixed(3)}</strong></p>
    <p>MNDWI: <strong>${Number(props.mndwi).toFixed(3)}</strong></p>
    <p>High-water prob: <strong>${(Number(props.high_prob) * 100).toFixed(1)}%</strong></p>
    <span class="tooltip-badge ${badge}">${props.predicted_label} potential</span>
  `;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Unable to load ${path} (${response.status})`);
  return response.json();
}

async function loadData() {
  const [aois, waterPoints, scenes, metrics] = await Promise.all([
    loadJson(`${DATA_BASE}/aois.geojson`),
    loadJson(`${DATA_BASE}/water_points.geojson`),
    loadJson(`${DATA_BASE}/scenes.json`),
    loadJson(`${DATA_BASE}/metrics.json`),
  ]);
  return { aois, waterPoints, scenes, metrics };
}

function getSelectedAoi() {
  return aoiInput.value;
}

function getFilteredPoints() {
  const selectedAoi = getSelectedAoi();
  return appData.waterPoints.features.filter(
    (feature) => selectedAoi === "ALL" || feature.properties.aoi === selectedAoi
  );
}

function getFilteredScenes() {
  const cloudThreshold = Number(cloudInput.value || 20);
  const tier = document.getElementById("tierInput").value;
  const selectedAoi = getSelectedAoi();
  return appData.scenes.filter(
    (scene) =>
      scene.cloud <= cloudThreshold &&
      scene.tier === tier &&
      (selectedAoi === "ALL" || scene.aoi === selectedAoi)
  );
}

function renderMetrics(points, scenes) {
  const season = document.getElementById("seasonInput").value;
  const cloudAvg =
    scenes.length > 0 ? scenes.reduce((sum, scene) => sum + scene.cloud, 0) / scenes.length : 0;

  document.getElementById("scenesDiscovered").textContent = String(appData.metrics.scenes_discovered);
  document.getElementById("scenesRetained").textContent = String(scenes.length);
  document.getElementById("avgCloud").textContent = `${cloudAvg.toFixed(1)}%`;
  document.getElementById("waterArea").textContent =
    season === "Wet Season"
      ? `${appData.metrics.water_area_wet_km2} km²`
      : `${appData.metrics.water_area_dry_km2} km²`;

  modelMetricsList.innerHTML = `
    <li><strong>Accuracy:</strong> ${(appData.metrics.model.accuracy * 100).toFixed(2)}%</li>
    <li><strong>Weighted F1:</strong> ${appData.metrics.model.weighted_f1.toFixed(4)}</li>
    <li><strong>Macro F1:</strong> ${appData.metrics.model.macro_f1.toFixed(4)}</li>
    <li><strong>Test samples:</strong> ${appData.metrics.model.test_samples}</li>
    <li><strong>Map points:</strong> ${points.length}</li>
  `;
}

function renderTable(rows) {
  sceneTableBody.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
        <tr>
          <td title="${row.scene_id}">${row.scene_id.slice(0, 18)}…</td>
          <td>${row.date}</td>
          <td>${Number(row.cloud).toFixed(1)}%</td>
          <td>${row.aoi_label}</td>
        </tr>
      `
        )
        .join("")
    : `<tr><td colspan="4">No scenes match current filters.</td></tr>`;
}

function renderAoiStats(points) {
  const grouped = points.reduce((acc, feature) => {
    const key = feature.properties.aoi;
    if (!acc[key]) acc[key] = [];
    acc[key].push(feature.properties);
    return acc;
  }, {});

  aoiStats.innerHTML = Object.keys(grouped)
    .sort()
    .map((aoi) => {
      const arr = grouped[aoi];
      const avgScore = arr.reduce((sum, item) => sum + Number(item.high_prob || 0), 0) / arr.length;
      return `<li><strong>${AOI_LABELS[aoi] || aoi}</strong> — ${arr.length} points, ${(avgScore * 100).toFixed(1)}% avg high-water</li>`;
    })
    .join("");
}

function clearLayers() {
  [regionLayer, classLayer, ndwiLayer, mndwiLayer].forEach((layer) => {
    if (layer) map.removeLayer(layer);
  });
}

function buildSoftRegions(aoiFeatures, points) {
  aoiScores = computeAoiScores(points);
  const pointCounts = points.reduce((acc, f) => {
    const key = f.properties.aoi;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  const softFeatures = aoiFeatures.map((feature) => {
    const ring = feature.geometry.coordinates[0];
    const softRing = softEllipseFromRing(ring);
    return {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [softRing] },
      properties: {
        ...feature.properties,
        score: aoiScores[feature.properties.aoi] || 0.35,
        pointCount: pointCounts[feature.properties.aoi] || 0,
      },
    };
  });

  return { type: "FeatureCollection", features: softFeatures };
}

function renderMap(points) {
  clearLayers();
  hideTooltip();

  const selectedAoi = getSelectedAoi();
  const aoiFeatures = appData.aois.features.filter(
    (f) => selectedAoi === "ALL" || f.properties.aoi === selectedAoi
  );

  const softRegions = buildSoftRegions(aoiFeatures, points);

  regionLayer = L.geoJSON(softRegions, {
    style: (feature) => {
      const score = feature.properties.score;
      const colors = scoreToColor(score);
      return {
        color: colors.stroke,
        weight: 1.5,
        opacity: 0.55,
        fillColor: colors.fill,
        fillOpacity: 0.28 + score * 0.18,
        className: "aoi-gradient-region",
      };
    },
    onEachFeature: (feature, layer) => bindRegionHover(feature, layer),
  });

  ndwiLayer = L.heatLayer(buildHeatPayload(points, "ndwi"), {
    radius: 42,
    blur: 28,
    minOpacity: 0.28,
    maxZoom: 12,
    gradient: {
      0.1: "#b8ecff",
      0.35: "#6ecfff",
      0.6: "#3a9ef5",
      0.82: "#2a6df0",
      1.0: "#f5c84c",
    },
  });

  mndwiLayer = L.heatLayer(buildHeatPayload(points, "mndwi"), {
    radius: 40,
    blur: 26,
    minOpacity: 0.22,
    maxZoom: 12,
    gradient: {
      0.1: "#b8f5e8",
      0.4: "#5eddb8",
      0.65: "#1fa89a",
      0.85: "#2a7fd4",
      1.0: "#f0e878",
    },
  });

  classLayer = L.geoJSON({ type: "FeatureCollection", features: points }, {
    pointToLayer: (feature, latlng) => {
      const label = feature.properties.predicted_label;
      const color = label === "High" ? "#f5c84c" : label === "Medium" ? "#4db4ff" : "#8ea8ff";
      return L.circleMarker(latlng, {
        radius: 6,
        color: "#fff",
        fillColor: color,
        fillOpacity: 0.92,
        weight: 2,
        className: "water-point-marker",
      });
    },
    onEachFeature: (feature, layer) => {
      layer.on("mouseover", (event) => {
        const container = map.getContainer().getBoundingClientRect();
        const x = event.originalEvent.clientX - container.left;
        const y = event.originalEvent.clientY - container.top;
        showTooltip(pointTooltip(feature.properties), x, y);
        layer.setStyle({ radius: 9, weight: 3 });
        layer.bringToFront();
      });
      layer.on("mousemove", (event) => {
        const container = map.getContainer().getBoundingClientRect();
        mapTooltip.style.left = `${event.originalEvent.clientX - container.left}px`;
        mapTooltip.style.top = `${event.originalEvent.clientY - container.top}px`;
      });
      layer.on("mouseout", () => {
        hideTooltip();
        layer.setStyle({ radius: 6, weight: 2 });
      });
    },
  });

  if (toggleNdwi.checked) ndwiLayer.addTo(map);
  if (toggleMndwi.checked) mndwiLayer.addTo(map);
  if (toggleRegions.checked) regionLayer.addTo(map);
  if (toggleClasses.checked) classLayer.addTo(map);

  const boundsSource = regionLayer.getBounds().isValid()
    ? regionLayer
    : L.geoJSON({ type: "FeatureCollection", features: points });
  map.fitBounds(boundsSource.getBounds(), { padding: [36, 36], animate: true, duration: 0.6 });
}

function bindLayerToggles() {
  const refreshLayer = (layer, enabled) => {
    if (!layer) return;
    if (enabled) layer.addTo(map);
    else map.removeLayer(layer);
  };

  toggleNdwi.addEventListener("change", () => refreshLayer(ndwiLayer, toggleNdwi.checked));
  toggleMndwi.addEventListener("change", () => refreshLayer(mndwiLayer, toggleMndwi.checked));
  toggleRegions.addEventListener("change", () => refreshLayer(regionLayer, toggleRegions.checked));
  toggleClasses.addEventListener("change", () => refreshLayer(classLayer, toggleClasses.checked));
}

function bindTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

function refreshDashboard() {
  const filteredPoints = getFilteredPoints();
  const filteredScenes = getFilteredScenes();
  renderMetrics(filteredPoints, filteredScenes);
  renderTable(filteredScenes);
  renderAoiStats(filteredPoints);
  renderMap(filteredPoints);
}

async function init() {
  cloudInput.addEventListener("input", () => {
    cloudValue.textContent = `${cloudInput.value}%`;
  });
  cloudValue.textContent = `${cloudInput.value}%`;

  bindTabs();

  try {
    appData = await loadData();
    bindLayerToggles();
    runBtn.addEventListener("click", refreshDashboard);
    aoiInput.addEventListener("change", refreshDashboard);
    document.getElementById("seasonInput").addEventListener("change", refreshDashboard);
    document.getElementById("tierInput").addEventListener("change", refreshDashboard);

    refreshDashboard();
    setTimeout(() => map.invalidateSize(), 120);
    window.addEventListener("resize", () => map.invalidateSize());
  } catch (error) {
    modelMetricsList.innerHTML = `<li><strong>Error:</strong> ${error.message}</li>
      <li>Run <code>python -m http.server 8000</code> and ensure <code>data/exports</code> exists.</li>`;
  }
}

init();
