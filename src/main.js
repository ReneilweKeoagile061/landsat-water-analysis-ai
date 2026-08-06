import { loadData } from "./api/loadData.js";
import { createMap, createMapController } from "./map/mapController.js";
import { filterPoints, filterScenes, readFiltersFromDom } from "./state/filters.js";
import { renderAoiStats, renderError, renderMetrics, renderTable } from "./ui/dashboard.js";
import { bindPanelToggle, bindTabs } from "./ui/tabs.js";
import { debounce } from "./utils/geo.js";
import { renderLoadStatus, setLoadingState } from "./utils/dom.js";
import "./styles.css";

let appData = null;
let mapController = null;
let shouldFitBounds = true;

function getToggles() {
  return {
    ndwi: document.getElementById("toggleNdwi"),
    mndwi: document.getElementById("toggleMndwi"),
    regions: document.getElementById("toggleRegions"),
    classes: document.getElementById("toggleClasses"),
  };
}

function refreshDashboard() {
  if (!appData?.isReady) return;

  const filters = readFiltersFromDom();
  const filteredPoints = filterPoints(appData.waterPoints.features, filters);
  const filteredScenes = filterScenes(appData.scenes, filters);

  renderMetrics(appData.metrics, filteredPoints, filteredScenes, filters.season);
  renderTable(filteredScenes);
  renderAoiStats(filteredPoints);
  mapController.updateMap({
    aois: appData.aois,
    points: filteredPoints,
    filters,
    fitBounds: shouldFitBounds,
  });
  shouldFitBounds = false;
}

async function bootstrap() {
  const cloudInput = document.getElementById("cloudInput");
  const cloudValue = document.getElementById("cloudValue");
  const runBtn = document.getElementById("runBtn");
  const retryBtn = document.getElementById("retryBtn");
  const map = createMap();
  const tooltipEl = document.getElementById("mapTooltip");

  bindTabs();
  bindPanelToggle();

  cloudInput?.addEventListener("input", () => {
    if (cloudValue) cloudValue.textContent = `${cloudInput.value}%`;
  });
  if (cloudValue && cloudInput) cloudValue.textContent = `${cloudInput.value}%`;

  const debouncedRefresh = debounce(refreshDashboard, 300);
  cloudInput?.addEventListener("input", debouncedRefresh);

  setLoadingState(true);
  appData = await loadData();
  setLoadingState(false);
  renderLoadStatus(appData.errors);

  if (!appData.isReady) {
    renderError("Unable to load required dashboard data. Check data exports and try again.");
    retryBtn?.addEventListener("click", () => window.location.reload());
    return;
  }

  mapController = createMapController(map, tooltipEl, getToggles());
  mapController.bindToggles();

  runBtn?.addEventListener("click", () => {
    shouldFitBounds = true;
    refreshDashboard();
  });

  ["aoiInput", "seasonInput", "tierInput"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      shouldFitBounds = true;
      refreshDashboard();
    });
  });

  refreshDashboard();
  setTimeout(() => mapController.invalidate(), 120);
  window.addEventListener("resize", () => mapController.invalidate());
}

bootstrap();
