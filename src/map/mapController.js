import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

window.L = L;

await import("leaflet.heat");
await import("leaflet.markercluster");

import { AOI_LABELS, HEATMAP_MAX_POINTS, HEATMAP_OFFSETS } from "../config.js";
import {
  computeAoiScores,
  minMax,
  normalize,
  sampleArray,
  scoreToColor,
  softEllipseFromRing,
} from "../utils/geo.js";
import { appendTooltipContent } from "../utils/dom.js";

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
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap &copy; CARTO",
  }).addTo(map);

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
  return {
    title: AOI_LABELS[props.aoi] || props.aoi,
    lines: [
      { label: "Scene", value: props.scene_id || "N/A" },
      { label: "NDWI", value: Number(props.ndwi).toFixed(3) },
      { label: "MNDWI", value: Number(props.mndwi).toFixed(3) },
      { label: "High-water prob", value: `${(Number(props.high_prob) * 100).toFixed(1)}%` },
    ],
    badgeText: `${props.predicted_label} potential`,
    badgeClass: badge,
  };
}

export function createMapController(map, tooltipEl, toggles) {
  let regionLayer = null;
  let classLayer = null;
  let ndwiLayer = null;
  let mndwiLayer = null;
  let lastBoundsKey = "";

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
    [regionLayer, classLayer, ndwiLayer, mndwiLayer].forEach((layer) => {
      if (layer) map.removeLayer(layer);
    });
  };

  const refreshLayer = (layer, enabled) => {
    if (!layer) return;
    if (enabled) layer.addTo(map);
    else map.removeLayer(layer);
  };

  const updateMap = ({ aois, points, filters, fitBounds = false }) => {
    clearLayers();
    hideTooltip();

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

    classLayer = L.markerClusterGroup({
      maxClusterRadius: 42,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    points.forEach((feature) => {
      const [lon, lat] = feature.geometry.coordinates;
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
    toggles.regions.addEventListener("change", () => refreshLayer(regionLayer, toggles.regions.checked));
    toggles.classes.addEventListener("change", () => refreshLayer(classLayer, toggles.classes.checked));
  };

  return { updateMap, bindToggles, invalidate: () => map.invalidateSize() };
}