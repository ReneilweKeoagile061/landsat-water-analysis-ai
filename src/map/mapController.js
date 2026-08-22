import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

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
  light: L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 20,
    maxNativeZoom: 19,
    attribution: "&copy; OpenStreetMap &copy; CARTO",
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
  const mapsUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat.toFixed(5)},${lon.toFixed(5)}`;
  const searchUrl = `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(5)},${lon.toFixed(5)}`;

  return `
    <div class="point-popup">
      <div class="popup-title">
        <strong>${label}</strong>
        <span class="tag ${props.predicted_label.toLowerCase()}">${props.predicted_label} Potential</span>
      </div>
      <div class="popup-action-highlight">
        🔎 <strong>${props.recommended_action || "Priority Investigation Site"}</strong>
      </div>
      <div class="popup-grid">
        <div><span>Depth to Water:</span> <strong>~${Number(props.depth_to_water_table_m || 45).toFixed(0)} m</strong></div>
        <div><span>Aquifer Yield:</span> <strong>${Number(props.aquifer_productivity_ls || 2.5).toFixed(1)} L/s</strong></div>
        <div><span>Borehole Score:</span> <strong>${(Number(props.borehole_feasibility_score || 0.65) * 100).toFixed(0)}%</strong></div>
        <div><span>Root-Zone Clay:</span> <strong>${Number(props.clay_fraction_pct || 20)}%</strong></div>
        <div><span>DTWT Class:</span> <strong>${props.dtwt_class || "N/A"}</strong></div>
        <div><span>Phreatophyte Index:</span> <strong>${props.phreatophyte_index != null ? `${(Number(props.phreatophyte_index) * 100).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>Infiltration:</span> <strong>${props.infiltration_score != null ? `${Number(props.infiltration_score).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>Evidence Confidence:</span> <strong>${props.evidence_confidence != null ? `${(Number(props.evidence_confidence) * 100).toFixed(0)}%` : "N/A"}</strong></div>
        <div><span>Slope / Elev:</span> <strong>${Number(props.slope || 1).toFixed(1)}° / ${Number(props.elevation || 1000).toFixed(0)}m</strong></div>
      </div>
      <div class="popup-aquifer">
        <span>Aquifer:</span> <em>${props.aquifer_type || "Karoo / Alluvial Sedimentary"}</em>
      </div>
      <div class="popup-aquifer">
        <span>Evidence:</span> <em>${props.subsurface_data_source || "Unverified"} (${props.subsurface_data_quality || "unknown quality"})</em>
      </div>
      <div class="popup-aquifer">
        <span>Next step:</span> <em>${props.validation_next_step || "Collect field measurements before drilling"}</em>
      </div>
      <div class="popup-coords">${lat.toFixed(4)}°, ${lon.toFixed(4)}°</div>
      <div class="popup-actions">
        <button type="button" class="popup-link report" data-report-id="${reportId}">📄 Download Site Report</button>
        <a href="${earthUrl}" target="_blank" rel="noopener noreferrer" class="popup-link earth">🌍 3D Google Earth Flyover</a>
        <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" class="popup-link street">🛰️ Google Street View</a>
        <a href="${searchUrl}" target="_blank" rel="noopener noreferrer" class="popup-link maps">🗺️ Google Maps Location</a>
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
    [regionLayer, classLayer, ndwiLayer, mndwiLayer, slopeLayer, dtwtLayer, boreholeLayer].forEach((layer) => {
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
    if (drawBtn) drawBtn.textContent = "✏️ Draw Property Boundary";
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

    const bestProps = analysis.bestBoreholePoint?.properties;
    const bestCoords = analysis.bestBoreholePoint?.geometry?.coordinates;

    content.append(
      el("p", "analysis-ha", `📐 Property Area: ${analysis.hectares.toLocaleString()} ha`),
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
        el("p", "subsurface-header", "⚡ Subsurface & Borehole Siting"),
        el("div", "subsurface-stat-row", `🎯 Borehole Feasibility: ${analysis.avgBoreholeScore}%`),
        el("div", "subsurface-stat-row", `💧 Depth to Water Table: ~${analysis.avgDtwt} m`),
        el("div", "subsurface-stat-row", `⚡ Expected Aquifer Yield: ~${analysis.avgProductivity} L/s`),
        el("div", "subsurface-stat-row", `🧱 Soil Clay / Sand: ${analysis.avgClay}% clay / ${100 - analysis.avgClay}% sand`),
        el("div", "subsurface-stat-row", `🌧 Infiltration Proxy: ${analysis.avgInfiltration}%`),
        el("div", "subsurface-stat-row", `📌 DTWT Class: ${analysis.dtwtClass}`)
      );

      if (bestCoords) {
        subCard.append(
          el(
            "div",
            "subsurface-target-coord",
            `📍 Prime Borehole Target: ${bestCoords[1].toFixed(4)}°, ${bestCoords[0].toFixed(4)}° (${bestProps?.recommended_action || "Recommended Target"})`
          )
        );
      }
      content.appendChild(subCard);
    }

    card.hidden = false;
    if (clearBtn) clearBtn.hidden = false;

    if (applyBtn) {
      applyBtn.onclick = () => {
        onApplyPropertyData?.(analysis);
      };
    }
  };

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

    const slopePoints = points.filter((feature) => Number.isFinite(Number(feature.properties.slope)));
    slopeLayer = L.heatLayer(buildHeatPayload(slopePoints.length ? slopePoints : points, "slope"), {
      radius: 38,
      blur: 24,
      minOpacity: 0.2,
      maxZoom: 12,
      gradient: {
        0.1: "#efe4c6",
        0.4: "#d4a056",
        0.7: "#b15a2a",
        1.0: "#6b2d12",
      },
    });

    const dtwtPoints = points.filter((f) => Number.isFinite(Number(f.properties.depth_to_water_table_m)));
    dtwtLayer = L.heatLayer(buildHeatPayload(dtwtPoints.length ? dtwtPoints : points, "depth_to_water_table_m"), {
      radius: 44,
      blur: 28,
      minOpacity: 0.24,
      maxZoom: 12,
      gradient: {
        0.1: "#c2e9fb",
        0.4: "#70c8f5",
        0.7: "#3b82f6",
        1.0: "#1e3a8a",
      },
    });

    const bPoints = points.filter((f) => Number.isFinite(Number(f.properties.borehole_feasibility_score)));
    boreholeLayer = L.heatLayer(buildHeatPayload(bPoints.length ? bPoints : points, "borehole_feasibility_score"), {
      radius: 42,
      blur: 26,
      minOpacity: 0.28,
      maxZoom: 12,
      gradient: {
        0.1: "#dcfce7",
        0.4: "#4ade80",
        0.7: "#16a34a",
        1.0: "#eab308",
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
        reportButton?.addEventListener("click", () => onDownloadReport?.(feature), { once: true });
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

    if (toggles.ndwi?.checked) ndwiLayer.addTo(map);
    if (toggles.mndwi?.checked) mndwiLayer.addTo(map);
    if (toggles.slope?.checked) slopeLayer.addTo(map);
    if (toggles.dtwt?.checked) dtwtLayer.addTo(map);
    if (toggles.borehole?.checked) boreholeLayer.addTo(map);
    if (toggles.regions?.checked) regionLayer.addTo(map);
    if (toggles.classes?.checked) classLayer.addTo(map);

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
    toggles.ndwi?.addEventListener("change", () => refreshLayer(ndwiLayer, toggles.ndwi.checked));
    toggles.mndwi?.addEventListener("change", () => refreshLayer(mndwiLayer, toggles.mndwi.checked));
    toggles.slope?.addEventListener("change", () => refreshLayer(slopeLayer, toggles.slope.checked));
    toggles.dtwt?.addEventListener("change", () => refreshLayer(dtwtLayer, toggles.dtwt.checked));
    toggles.borehole?.addEventListener("change", () => refreshLayer(boreholeLayer, toggles.borehole.checked));
    toggles.regions?.addEventListener("change", () => refreshLayer(regionLayer, toggles.regions.checked));
    toggles.classes?.addEventListener("change", () => refreshLayer(classLayer, toggles.classes.checked));

    document.querySelectorAll("input[name='baseMapRadio']").forEach((radio) => {
      radio.addEventListener("change", (e) => {
        if (e.target.checked) switchBaseMap(e.target.value);
      });
    });

    const drawBtn = document.getElementById("drawPropertyBtn");
    const finishBtn = document.getElementById("finishDrawBtn");
    const clearBtn = document.getElementById("clearDrawBtn");
    const closeAnalysisBtn = document.getElementById("closeAnalysisBtn");

    drawBtn?.addEventListener("click", () => {
      isDrawing = !isDrawing;
      if (isDrawing) {
        map.getContainer().style.cursor = "crosshair";
        drawBtn.textContent = "✕ Cancel Drawing";
      } else {
        map.getContainer().style.cursor = "";
        drawBtn.textContent = "✏️ Draw Property Boundary";
      }
    });

    finishBtn?.addEventListener("click", finishDrawing);
    clearBtn?.addEventListener("click", clearDrawnProperty);
    closeAnalysisBtn?.addEventListener("click", () => {
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

