import { loadData } from "./api/loadData.js";
import { createMap, createMapController } from "./map/mapController.js";
import { filterPoints, filterScenes, readFiltersFromDom } from "./state/filters.js";
import {
  renderAoiStats,
  renderSubsurfaceSummary,
  downloadSiteReport,
  renderError,
  renderMetrics,
  renderTable,
  bindWaterGainCalculator,
  applyPropertyAnalysisToCalculator,
} from "./ui/dashboard.js";
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
    slope: document.getElementById("toggleSlope"),
    dtwt: document.getElementById("toggleDtwt"),
    borehole: document.getElementById("toggleBorehole"),
    bgiBoreholes: document.getElementById("toggleBgiBoreholes"),
    drillTargets: document.getElementById("toggleDrillTargets"),
    regions: document.getElementById("toggleRegions"),
    classes: document.getElementById("toggleClasses"),
  };
}

function refreshDashboard() {
  if (!appData.isReady) return;

  const filters = readFiltersFromDom();
  const filteredPoints = filterPoints(appData.waterPoints.features, filters);
  const filteredScenes = filterScenes(appData.scenes, filters);

  renderMetrics(appData.metrics, filteredPoints, filteredScenes, filters.season);
  renderTable(filteredScenes);
  renderAoiStats(filteredPoints);
  renderSubsurfaceSummary(filteredPoints);
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
  bindWaterGainCalculator();

  // Note: toggles default values come from the HTML `checked` attributes.
  // Do NOT reset them here — mapController reads them on init.

  cloudInput.addEventListener("input", () => {
    if (cloudValue) cloudValue.textContent = `${cloudInput.value}%`;
  });
  if (cloudValue && cloudInput) cloudValue.textContent = `${cloudInput.value}%`;

  const potentialInput = document.getElementById("potentialInput");
  const potentialValue = document.getElementById("potentialValue");
  const primeToggleBtn = document.getElementById("primeWaterToggle");

  const syncPotentialUi = (val) => {
    const num = Number(val);
    if (potentialInput) potentialInput.value = String(num);
    if (potentialValue) {
      potentialValue.textContent = num === 0 ? "0% (All Points)" : `>=${num}% Confidence`;
    }
    document.querySelectorAll(".preset-pill").forEach((pill) => {
      pill.classList.toggle("active", Number(pill.dataset.potential) === num);
    });
    if (primeToggleBtn) {
      primeToggleBtn.classList.toggle("active", num >= 90);
      primeToggleBtn.textContent = num >= 90 ? "Prime Active (>=90%)" : "Prime Siting (>=90%)";
    }
  };

  potentialInput.addEventListener("input", () => {
    syncPotentialUi(potentialInput.value);
  });
  if (potentialInput) syncPotentialUi(potentialInput.value);

  document.querySelectorAll(".preset-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const val = Number(pill.dataset.potential);
      syncPotentialUi(val);
      refreshDashboard();
    });
  });

  primeToggleBtn.addEventListener("click", () => {
    const current = Number(potentialInput?.value || 0);
    const next = current >= 90 ? 0 : 90;
    syncPotentialUi(next);
    refreshDashboard();
  });

  const debouncedRefresh = debounce(refreshDashboard, 300);
  cloudInput.addEventListener("input", debouncedRefresh);
  potentialInput.addEventListener("input", debouncedRefresh);

  setLoadingState(true);
  appData = await loadData();
  setLoadingState(false);
  renderLoadStatus(appData.errors);

  // Demo data guard — must run before any rendering
  if (appData.metrics?.is_demo_data) {
    const warning = appData.metrics.demo_data_warning ||
      "⚠ DEMO DATA: All map points are randomly simulated and do NOT represent real observations.";
    console.error("[DEMO DATA]", warning);
    const banner = document.createElement("div");
    banner.id = "demoBanner";
    banner.setAttribute("role", "alert");
    banner.style.cssText = [
      "position:fixed", "top:0", "left:0", "right:0", "z-index:9999",
      "background:#b91c1c", "color:#fff", "font-weight:600",
      "padding:10px 16px", "text-align:center", "font-size:0.9rem",
      "letter-spacing:0.02em", "box-shadow:0 2px 8px rgba(0,0,0,0.4)",
    ].join(";");
    banner.textContent = warning;
    document.body.prepend(banner);
  }

  if (!appData.isReady) {
    renderError("Unable to load required dashboard data. Check data exports and try again.");
    retryBtn.addEventListener("click", () => window.location.reload());
    return;
  }

  mapController = createMapController(map, tooltipEl, getToggles(), applyPropertyAnalysisToCalculator, downloadSiteReport);
  mapController.bindToggles();

  runBtn.addEventListener("click", () => {
    shouldFitBounds = true;
    refreshDashboard();
  });

  ["aoiInput", "seasonInput", "tierInput"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      shouldFitBounds = true;
      refreshDashboard();
    });
  });

  refreshDashboard();
  setTimeout(() => mapController.invalidate(), 120);
  window.addEventListener("resize", () => mapController.invalidate());
}

bootstrap();
