import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

window.L = L;

await import("leaflet.heat");
await import("leaflet.markercluster");

import { AOI_LABELS, HEATMAP_MAX_POINTS, HEATMAP_OFFSETS } from "../config.js";
import {
  analyzePolygonWaterPotential,
  computeAoiScores,
  minMax,
  normalize,
  sampleArray,
  scoreToColor,
  softEllipseFromRing,
} from "../utils/geo.js";
import { appendTooltipContent, clearElement, el } from "../utils/dom.js";

const BASE_LAYERS = {
  light: L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      maxNativeZoom: 16,
      attribution: "&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
    }
  ),
  osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }),
  satellite: L.tileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", {
    maxZoom: 20,
    maxNativeZoom: 19,
    attribution: "Map data &copy; Google",
  }),
  esri: L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 20,
      maxNativeZoom: 17,
      attribution: "Tiles &copy; Esri, DigitalGlobe, Earthstar Geographics",
    }
  ),
  topo: L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    maxZoom: 20,
    maxNativeZoom: 16,
    attribution: "Map data &copy; OpenStreetMap, SRTM | Map style &copy; OpenTopoMap (CC-BY-SA)",
  }),
};

export function createMap() {
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
  BASE_LAYERS.light.addTo(map);

  return map;
}

function buildHeatPayload(points, key) {
  const sampled = sampleArray(points, HEATMAP_MAX_POINTS);
  const values = sampled.map((feature) => Number(feature.properties[key]));
  const { min, max } = minMax(values);
  const payload = [];

  sampled.forEach((feature) => {
    const [lon, lat] = feature.geometry.coordinates;
    const base = normalize(Number(feature.properties[key]), min, max);
    payload.push([lat, lon, base]);

    HEATMAP_OFFSETS.forEach(([dLat, dLon], index) => {
      payload.push([lat + dLat, lon + dLon, base * (0.72 - index * 0.06)]);
    });
  });

  return payload;
}

function buildSoftRegions(aoiFeatures, points) {
  const aoiScores = computeAoiScores(points);
  const pointCounts = points.reduce((acc, feature) => {
    const key = feature.properties.aoi;
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

function regionTooltipContent(feature) {
  const { aoi, score, pointCount } = feature.properties;
  const label = AOI_LABELS[aoi] || aoi;
  const badge = score >= 0.7 ? "high" : score >= 0.45 ? "medium" : "low";
  const potential = badge.charAt(0).toUpperCase() + badge.slice(1);
  return {
    title: label,
    lines: [
      { label: "Avg high-water probability", value: `${(score * 100).toFixed(1)}%` },
      { label: "Sample points", value: String(pointCount) },
    ],
    badgeText: `${potential} potential region`,
    badgeClass: badge,
  };
}

function pointTooltipContent(props) {
  const badge = props.predicted_label.toLowerCase();
  const lines = [
    { label: "Target Siting", value: props.recommended_action || `${props.predicted_label} potential` },
    { label: "Water Table Depth", value: props.depth_to_water_table_m ? `~${Number(props.depth_to_water_table_m).toFixed(0)} m` : "N/A" },
    { label: "Borehole Feasibility", value: props.borehole_feasibility_score ? `${(Number(props.borehole_feasibility_score) * 100).toFixed(0)}%` : "N/A" },
    { label: "Aquifer Yield", value: props.aquifer_productivity_ls ? `${Number(props.aquifer_productivity_ls).toFixed(1)} L/s` : "N/A" },
  ];
  return {
    title: AOI_LABELS[props.aoi] || props.aoi,
    lines,
    badgeText: `${props.predicted_label} potential`,
    badgeClass: badge,
  };
}

function buildPointPopupHtml(feature, reportId) {
  const props = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  const label = AOI_LABELS[props.aoi] || props.aoi;
  const earthUrl = `https://earth.google.com/web/@${lat.toFixed(5)},${lon.toFixed(5)},1000a,2000d,35y,0t,0r`;
  const mapsUrl = `https://www.google.com/maps/@api=1&map_action=pano&viewpoint=${lat.toFixed(5)},${lon.toFixed(5)}`;
  const searchUrl = `https://www.google.com/maps/search/api=1&query=${lat.toFixed(5)},${lon.toFixed(5)}`;

  const isClayHazard = (props.clay_fraction_pct != null && Number(props.clay_fraction_pct) > 35) || props.clay_shielding_hazard;
  const targetDepth = Number(props.depth_to_water_table_m || 45);
  const vesAbMin = Math.max(3 * targetDepth, Math.round(targetDepth / 0.19));

  return `
    <div class="point-popup">
      <div class="popup-title">
        <strong>${label}</strong>
        <span class="tag ${props.predicted_label.toLowerCase()}">${props.predicted_label} Potential</span>
      </div>
      <div class="popup-action-highlight">
         <strong>${props.recommended_action || "Priority Investigation Site"}</strong>
      </div>
      ${
        isClayHazard
          ? `<div class="clay-hazard-badge" style="background:#fef2f2; color:#b91c1c; border:1px solid #f87171; border-radius:4px; padding:4px 6px; font-size:0.75rem; margin-bottom:6px;">
              <strong>Conductive Clay Shielding Hazard (&lt;10 Ω·m)</strong><br>Heavy clay seals recharge. Lined earth dams/ponds recommended over deep drilling.
            </div>`
          : ""
      }
      <div class="popup-grid">
        <div><span>Depth to Water:</span> <strong>~${Number(props.depth_to_water_table_m || 45).toFixed(0)} m</strong></div>
        <div><span>Aquifer Yield:</span> <strong>${Number(props.aquifer_productivity_ls || 2.5).toFixed(1)} L/s</strong></div>
        <div><span>Borehole Score:</span> <strong>${(Number(props.borehole_feasibility_score || 0.65) * 100).toFixed(0)}%</strong></div>
        <div><span>Root-Zone Clay:</span> <strong>${Number(props.clay_fraction_pct || 20)}%</strong></div>
        <div><span>DTWT Class:</span> <strong>${props.dtwt_class || "N/A"}</strong></div>
        <div><span>Phreatophyte:</span> <strong>${props.phreatophyte_index != null ? `${(Number(props.phreatophyte_index) * 100).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>Infiltration:</span> <strong>${props.infiltration_score != null ? `${Number(props.infiltration_score).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>Evidence Trust:</span> <strong>${props.evidence_confidence != null ? `${(Number(props.evidence_confidence) * 100).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>VES Cable AB:</span> <strong>≥ ${vesAbMin} m</strong></div>
      </div>
      <div class="popup-aquifer">
        <span>Aquifer:</span> <em>${props.aquifer_type || "Karoo / Alluvial Sedimentary"}</em>
      </div>
      <div class="popup-aquifer">
        <span>Evidence:</span> <em>${props.subsurface_data_source || "Unverified"} (${props.subsurface_data_quality || "screening"})</em>
      </div>
      <div class="popup-aquifer">
        <span>Next step:</span> <em>${props.validation_next_step || `Schlumberger VES survey (AB ≥ ${vesAbMin} m)`}</em>
      </div>
      <div class="popup-coords">${lat.toFixed(4)}°, ${lon.toFixed(4)}°</div>
      <div class="popup-actions">
        <button type="button" class="popup-link report" data-report-id="${reportId}"> Download Site Dossier</button>
        <a href="${earthUrl}" target="_blank" rel="noopener noreferrer" class="popup-link earth"> 3D Google Earth Flyover</a>
        <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" class="popup-link street">️ Google Street View</a>
        <a href="${searchUrl}" target="_blank" rel="noopener noreferrer" class="popup-link maps">️ Google Maps Location</a>
      </div>
    </div>
  `;
}

export function createMapController(map, tooltipEl, toggles, onApplyPropertyData, onDownloadReport) {
  let regionLayer = null;
  let classLayer = null;
  let ndwiLayer = null;
  let mndwiLayer = null;
  let slopeLayer = null;
  let dtwtLayer = null;
  let boreholeLayer = null;
  let bgiBoreholeLayer = null;
  let drillTargetLayer = null;
  let activeBaseLayer = "light";
  let lastBoundsKey = "";
  let currentPoints = [];

  // Property drawing state
  let isDrawing = false;
  let drawPoints = [];
  let drawMarkers = [];
  let drawPolyline = null;
  let drawnPolygonLayer = null;

  const hideTooltip = () => {
    tooltipEl.hidden = true;
  };

  const showTooltip = (content, x, y) => {
    appendTooltipContent(tooltipEl, content);
    tooltipEl.hidden = false;
    tooltipEl.style.left = `${x}px`;
    tooltipEl.style.top = `${y}px`;
  };

  const clearLayers = () => {
    [regionLayer, classLayer, ndwiLayer, mndwiLayer, slopeLayer, dtwtLayer, boreholeLayer, bgiBoreholeLayer, drillTargetLayer].forEach((layer) => {
      if (layer) map.removeLayer(layer);
    });
  };

  const refreshLayer = (layer, enabled) => {
    if (!layer) return;
    if (enabled) layer.addTo(map);
    else map.removeLayer(layer);
  };

  const switchBaseMap = (name) => {
    if (BASE_LAYERS[activeBaseLayer]) {
      map.removeLayer(BASE_LAYERS[activeBaseLayer]);
    }
    if (BASE_LAYERS[name]) {
      BASE_LAYERS[name].addTo(map);
      activeBaseLayer = name;
    }
  };

  const clearDrawnProperty = () => {
    drawPoints = [];
    drawMarkers.forEach((m) => map.removeLayer(m));
    drawMarkers = [];
    if (drawPolyline) {
      map.removeLayer(drawPolyline);
      drawPolyline = null;
    }
    if (drawnPolygonLayer) {
      map.removeLayer(drawnPolygonLayer);
      drawnPolygonLayer = null;
    }
    const card = document.getElementById("drawAnalysisCard");
    if (card) card.hidden = true;
    const finishBtn = document.getElementById("finishDrawBtn");
    const clearBtn = document.getElementById("clearDrawBtn");
    if (finishBtn) finishBtn.hidden = true;
    if (clearBtn) clearBtn.hidden = true;
  };

  const finishDrawing = () => {
    if (drawPoints.length < 3) {
      alert("Please place at least 3 points to define a property polygon.");
      return;
    }

    isDrawing = false;
    map.getContainer().style.cursor = "";
    const drawBtn = document.getElementById("drawPropertyBtn");
    const finishBtn = document.getElementById("finishDrawBtn");
    if (drawBtn) drawBtn.textContent = "️ Draw Property Boundary";
    if (finishBtn) finishBtn.hidden = true;

    // Build closed ring [ [lon, lat], ... ]
    const ring = drawPoints.map(([lat, lon]) => [lon, lat]);
    ring.push(ring[0]);

    if (drawPolyline) {
      map.removeLayer(drawPolyline);
      drawPolyline = null;
    }
    drawMarkers.forEach((m) => map.removeLayer(m));
    drawMarkers = [];

    if (drawnPolygonLayer) map.removeLayer(drawnPolygonLayer);
    drawnPolygonLayer = L.polygon(drawPoints, {
      color: "#f5c84c",
      weight: 3,
      fillColor: "#2ec9c5",
      fillOpacity: 0.35,
      dashArray: "6, 6",
    }).addTo(map);

    const analysis = analyzePolygonWaterPotential(ring, currentPoints);
    showAnalysisResult(analysis);
  };

  const showAnalysisResult = (analysis) => {
    const card = document.getElementById("drawAnalysisCard");
    const content = document.getElementById("drawAnalysisContent");
    const clearBtn = document.getElementById("clearDrawBtn");
    const applyBtn = document.getElementById("applyToCalcBtn");

    if (!card || !content) return;
    clearElement(content);

    const bestProps = analysis.bestBoreholePoint.properties;
    const bestCoords = analysis.bestBoreholePoint.geometry.coordinates;

    content.append(
      el("p", "analysis-ha", ` Property Area: ${analysis.hectares.toLocaleString()} ha`),
      el("p", "analysis-samples", `Sampled from ${analysis.sampleCount} satellite & hydrogeology points:`),
      el(
        "div",
        "analysis-breakdown",
        `Surface Potential: High ${analysis.shares.High}% | Med ${analysis.shares.Medium}% | Low ${analysis.shares.Low}%`
      )
    );

    if (analysis.sampleCount > 0) {
      const subCard = el("div", "analysis-subsurface-box");
      subCard.append(
        el("p", "subsurface-header", " Subsurface & Borehole Siting"),
        el("div", "subsurface-stat-row", ` Borehole Feasibility: ${analysis.avgBoreholeScore}%`),
        el("div", "subsurface-stat-row", ` Depth to Water Table: ~${analysis.avgDtwt} m`),
        el("div", "subsurface-stat-row", ` Expected Aquifer Yield: ~${analysis.avgProductivity} L/s`),
        el("div", "subsurface-stat-row", ` Soil Clay / Sand: ${analysis.avgClay}% clay / ${100 - analysis.avgClay}% sand`),
        el("div", "subsurface-stat-row", ` Infiltration Proxy: ${analysis.avgInfiltration}%`),
        el("div", "subsurface-stat-row", ` DTWT Class: ${analysis.dtwtClass}`)
      );

      if (bestCoords) {
        subCard.append(
          el(
            "div",
            "subsurface-target-coord",
            ` Prime Borehole Target: ${bestCoords[1].toFixed(4)}°, ${bestCoords[0].toFixed(4)}° (${bestProps.recommended_action || "Recommended Target"})`
          )
        );
      }
      content.appendChild(subCard);
    }

    card.hidden = false;
    if (clearBtn) clearBtn.hidden = false;

    if (applyBtn) {
      applyBtn.onclick = () => {
        onApplyPropertyData(analysis);
      };
    }
  };

  const loadBGIBoreholes = async () => {
    try {
      const res = await fetch("/data/boreholes/bgi_verified_boreholes.csv");
      const text = await res.text();
      const lines = text.trim().split("\n");
      const headers = lines[0].split(",");

      bgiBoreholeLayer = L.markerClusterGroup({
        maxClusterRadius: 40,
        spiderfyOnMaxZoom: true,
      });

      for (let i = 1; i < lines.length; i++) {
        const row = lines[i].split(",");
        const data = {};
        headers.forEach((h, idx) => (data[h] = row[idx]));
        if (!data.latitude || !data.longitude) continue;

        const isProd = data.is_productive === "1";
        const color = isProd ? "#10b981" : "#ef4444";
        const fill = isProd ? "#34d399" : "#f87171";

        const marker = L.circleMarker([Number(data.latitude), Number(data.longitude)], {
          radius: 6,
          color: color,
          fillColor: fill,
          fillOpacity: 0.8,
          weight: 2,
        });

        marker.bindPopup(`
          <div class="point-popup">
            <div class="popup-title"><strong>BGI ID: ${data.borehole_id}</strong></div>
            <div><span>Location:</span> <strong>${data.location}</strong></div>
            <div><span>Yield:</span> <strong>${data.yield_m3h} m³/h</strong></div>
            <div><span>Water Strike:</span> <strong>${data.water_strike_m} m</strong></div>
            <div><span>Productive:</span> <strong>${isProd ? "Yes" : "No"}</strong></div>
          </div>
        `, { className: "leaflet-custom-popup", maxWidth: 280 });

        bgiBoreholeLayer.addLayer(marker);
      }
      if (toggles.bgiBoreholes.checked) bgiBoreholeLayer.addTo(map);
    } catch (e) {
      console.warn("Could not load BGI boreholes:", e);
    }
  };

  const loadRankedDrillTargets = async () => {
    try {
      const res = await fetch("/data/exports/ranked_drill_targets.json");
      const targets = await res.json();

      drillTargetLayer = L.layerGroup();
      
      const rankColors = { 1: "#fbbf24", 2: "#94a3b8", 3: "#b45309" }; // Gold, Silver, Bronze
      const rankIcons = { 1: "", 2: "", 3: "" };

      targets.forEach(t => {
        const rank = t.target_rank || t.rank || 1;
        const color = rankColors[rank] || "#3b82f6";
        const mlScore = t.ml_prospectivity_score || t.ml_score || 0;
        const prioScore = t.final_priority_score || t.priority_score || 0;
        const action = t.recommended_action || t.ert_recommendation || "ERT Geophysics survey line recommended";
        
        // Marker
        const htmlIcon = L.divIcon({
          html: `<div style="font-size: 16px; background: white; border: 2px solid ${color}; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${rankIcons[rank] || ""}</div>`,
          className: "",
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });

        const marker = L.marker([t.latitude, t.longitude], { icon: htmlIcon });
        marker.bindPopup(`
          <div class="point-popup">
            <div class="popup-title"><strong>Rank ${rank} Target</strong></div>
            <div><span>ML Score:</span> <strong>${(mlScore * 100).toFixed(1)}%</strong></div>
            <div><span>Priority Score:</span> <strong>${(prioScore * 100).toFixed(1)}%</strong></div>
            <div><span>Recommendation:</span> <strong>${action}</strong></div>
          </div>
        `, { className: "leaflet-custom-popup", maxWidth: 280 });

        drillTargetLayer.addLayer(marker);

        // ERT radius circle (100m)
        const circle = L.circle([t.latitude, t.longitude], {
          radius: 100,
          color: color,
          weight: 1,
          fillColor: color,
          fillOpacity: 0.1,
          dashArray: "4 4"
        });
        drillTargetLayer.addLayer(circle);
      });

      if (toggles.drillTargets.checked) drillTargetLayer.addTo(map);
    } catch (e) {
      console.warn("Could not load ranked drill targets:", e);
    }
  };

  // Initial load
  loadBGIBoreholes();
  loadRankedDrillTargets();


  const handleMapClick = (event) => {
    if (!isDrawing) return;
    const { lat, lng } = event.latlng;
    drawPoints.push([lat, lng]);

    const marker = L.circleMarker([lat, lng], {
      radius: 5,
      color: "#fff",
      fillColor: "#1b8fe8",
      fillOpacity: 1,
      weight: 2,
    }).addTo(map);
    drawMarkers.push(marker);

    if (drawPolyline) {
      drawPolyline.setLatLngs(drawPoints);
    } else {
      drawPolyline = L.polyline(drawPoints, { color: "#1b8fe8", weight: 2.5, dashArray: "4, 4" }).addTo(map);
    }

    const finishBtn = document.getElementById("finishDrawBtn");
    const clearBtn = document.getElementById("clearDrawBtn");
    if (drawPoints.length >= 3 && finishBtn) finishBtn.hidden = false;
    if (clearBtn) clearBtn.hidden = false;
  };

  const updateMap = ({ aois, points, filters, fitBounds = false }) => {
    clearLayers();
    hideTooltip();
    currentPoints = points;

    const aoiFeatures = aois.features.filter(
      (feature) => filters.aoi === "ALL" || feature.properties.aoi === filters.aoi
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
      onEachFeature: (feature, layer) => {
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
          showTooltip(
            regionTooltipContent(feature),
            event.originalEvent.clientX - container.left,
            event.originalEvent.clientY - container.top
          );
          layer.setStyle({ fillOpacity: 0.52, weight: 2.5, opacity: 0.85 });
        });
        layer.on("mousemove", (event) => {
          const container = map.getContainer().getBoundingClientRect();
          tooltipEl.style.left = `${event.originalEvent.clientX - container.left}px`;
          tooltipEl.style.top = `${event.originalEvent.clientY - container.top}px`;
        });
        layer.on("mouseout", () => {
          hideTooltip();
          layer.setStyle(baseStyle());
        });
      },
    });

    ndwiLayer = L.heatLayer(buildHeatPayload(points, "ndwi"), {
      radius: 46,
      blur: 30,
      minOpacity: 0.32,
      maxZoom: 14,
      gradient: {
        0.05: "#0a192f",
        0.2: "#0284c7",
        0.4: "#06b6d4",
        0.6: "#10b981",
        0.8: "#84cc16",
        1.0: "#facc15",
      },
    });

    mndwiLayer = L.heatLayer(buildHeatPayload(points, "mndwi"), {
      radius: 44,
      blur: 28,
      minOpacity: 0.28,
      maxZoom: 14,
      gradient: {
        0.1: "#082f49",
        0.3: "#0369a1",
        0.55: "#0284c7",
        0.8: "#38bdf8",
        1.0: "#e0f2fe",
      },
    });

    const slopePoints = points.filter((feature) => Number.isFinite(Number(feature.properties.slope)));
    slopeLayer = L.heatLayer(buildHeatPayload(slopePoints.length ? slopePoints : points, "slope"), {
      radius: 42,
      blur: 26,
      minOpacity: 0.25,
      maxZoom: 14,
      gradient: {
        0.05: "#1e1b4b",
        0.25: "#312e81",
        0.45: "#0284c7",
        0.65: "#f59e0b",
        0.85: "#ea580c",
        1.0: "#dc2626",
      },
    });

    const dtwtPoints = points.filter((f) => Number.isFinite(Number(f.properties.depth_to_water_table_m)));
    dtwtLayer = L.heatLayer(buildHeatPayload(dtwtPoints.length ? dtwtPoints : points, "depth_to_water_table_m"), {
      radius: 48,
      blur: 32,
      minOpacity: 0.3,
      maxZoom: 14,
      gradient: {
        0.05: "#030712",
        0.25: "#1e3a8a",
        0.5: "#2563eb",
        0.75: "#38bdf8",
        1.0: "#a5f3fc",
      },
    });

    const bPoints = points.filter((f) => Number.isFinite(Number(f.properties.borehole_feasibility_score)));
    boreholeLayer = L.heatLayer(buildHeatPayload(bPoints.length ? bPoints : points, "borehole_feasibility_score"), {
      radius: 46,
      blur: 28,
      minOpacity: 0.3,
      maxZoom: 14,
      gradient: {
        0.05: "#022c22",
        0.3: "#047857",
        0.55: "#10b981",
        0.8: "#4ade80",
        1.0: "#fde047",
      },
    });

    classLayer = L.markerClusterGroup({
      maxClusterRadius: 42,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    points.forEach((feature, index) => {
      const [lon, lat] = feature.geometry.coordinates;
      const reportId = `site-report-${index}`;
      const label = feature.properties.predicted_label;
      const color = label === "High" ? "#f5c84c" : label === "Medium" ? "#4db4ff" : "#8ea8ff";
      const marker = L.circleMarker([lat, lon], {
        radius: 6,
        color: "#fff",
        fillColor: color,
        fillOpacity: 0.92,
        weight: 2,
        className: "water-point-marker",
      });

      marker.bindPopup(buildPointPopupHtml(feature, reportId), {
        className: "leaflet-custom-popup",
        maxWidth: 320,
      });

      marker.on("popupopen", () => {
        const reportButton = document.querySelector(`[data-report-id="${reportId}"]`);
        reportButton.addEventListener("click", () => onDownloadReport(feature), { once: true });
      });

      marker.on("mouseover", (event) => {
        const container = map.getContainer().getBoundingClientRect();
        showTooltip(
          pointTooltipContent(feature.properties),
          event.originalEvent.clientX - container.left,
          event.originalEvent.clientY - container.top
        );
        marker.setStyle({ radius: 9, weight: 3 });
      });
      marker.on("mousemove", (event) => {
        const container = map.getContainer().getBoundingClientRect();
        tooltipEl.style.left = `${event.originalEvent.clientX - container.left}px`;
        tooltipEl.style.top = `${event.originalEvent.clientY - container.top}px`;
      });
      marker.on("mouseout", () => {
        hideTooltip();
        marker.setStyle({ radius: 6, weight: 2 });
      });

      classLayer.addLayer(marker);
    });

    if (toggles.ndwi.checked) ndwiLayer.addTo(map);
    if (toggles.mndwi.checked) mndwiLayer.addTo(map);
    if (toggles.slope.checked) slopeLayer.addTo(map);
    if (toggles.dtwt.checked) dtwtLayer.addTo(map);
    if (toggles.borehole.checked) boreholeLayer.addTo(map);
    if (toggles.bgiBoreholes.checked && bgiBoreholeLayer) bgiBoreholeLayer.addTo(map);
    if (toggles.drillTargets.checked && drillTargetLayer) drillTargetLayer.addTo(map);
    if (toggles.regions.checked) regionLayer.addTo(map);
    if (toggles.classes.checked) classLayer.addTo(map);

    const boundsKey = `${filters.aoi}-${filters.season}-${filters.tier}-${points.length}`;
    if (fitBounds || boundsKey !== lastBoundsKey) {
      const boundsSource = regionLayer.getBounds().isValid()
        ? regionLayer
        : L.geoJSON({ type: "FeatureCollection", features: points });
      if (boundsSource.getBounds().isValid()) {
        map.fitBounds(boundsSource.getBounds(), { padding: [36, 36], animate: true, duration: 0.6 });
        lastBoundsKey = boundsKey;
      }
    }
  };

  const bindToggles = () => {
    toggles.ndwi.addEventListener("change", () => refreshLayer(ndwiLayer, toggles.ndwi.checked));
    toggles.mndwi.addEventListener("change", () => refreshLayer(mndwiLayer, toggles.mndwi.checked));
    toggles.slope.addEventListener("change", () => refreshLayer(slopeLayer, toggles.slope.checked));
    toggles.dtwt.addEventListener("change", () => refreshLayer(dtwtLayer, toggles.dtwt.checked));
    toggles.borehole.addEventListener("change", () => refreshLayer(boreholeLayer, toggles.borehole.checked));
    toggles.bgiBoreholes.addEventListener("change", () => refreshLayer(bgiBoreholeLayer, toggles.bgiBoreholes.checked));
    toggles.drillTargets.addEventListener("change", () => refreshLayer(drillTargetLayer, toggles.drillTargets.checked));
    toggles.regions.addEventListener("change", () => refreshLayer(regionLayer, toggles.regions.checked));
    toggles.classes.addEventListener("change", () => refreshLayer(classLayer, toggles.classes.checked));

    document.querySelectorAll("input[name='baseMapRadio']").forEach((radio) => {
      radio.addEventListener("change", (e) => {
        if (e.target.checked) switchBaseMap(e.target.value);
      });
    });

    const drawBtn = document.getElementById("drawPropertyBtn");
    const finishBtn = document.getElementById("finishDrawBtn");
    const clearBtn = document.getElementById("clearDrawBtn");
    const closeAnalysisBtn = document.getElementById("closeAnalysisBtn");

    drawBtn.addEventListener("click", () => {
      isDrawing = !isDrawing;
      if (isDrawing) {
        map.getContainer().style.cursor = "crosshair";
        drawBtn.textContent = " Cancel Drawing";
      } else {
        map.getContainer().style.cursor = "";
        drawBtn.textContent = "️ Draw Property Boundary";
      }
    });

    finishBtn.addEventListener("click", finishDrawing);
    clearBtn.addEventListener("click", clearDrawnProperty);
    closeAnalysisBtn.addEventListener("click", () => {
      const card = document.getElementById("drawAnalysisCard");
      if (card) card.hidden = true;
    });

    map.on("click", handleMapClick);
    map.on("dblclick", (e) => {
      if (isDrawing && drawPoints.length >= 3) {
        L.DomEvent.stop(e);
        finishDrawing();
      }
    });
  };

  return {
    updateMap,
    bindToggles,
    invalidate: () => map.invalidateSize(),
    clearDrawnProperty,
  };
}

