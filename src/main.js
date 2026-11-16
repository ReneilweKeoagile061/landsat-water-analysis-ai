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
  bindRoiCalculator,
  applyPropertyAnalysisToCalculator,
} from "./ui/dashboard.js";
import { bindPanelToggle, bindTabs } from "./ui/tabs.js";
import { debounce } from "./utils/geo.js";
import { renderLoadStatus, setLoadingState } from "./utils/dom.js";
import { auth } from "./auth/authManager.js";
import { initLandingPage } from "./ui/landingPage.js";
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
    geeNdwi: document.getElementById("toggleGeeNdwi"),
    geeSar: document.getElementById("toggleGeeSar"),
    geeTwi: document.getElementById("toggleGeeTwi"),
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

function updateUserProfileUi(user) {
  const nameEl = document.getElementById("topbarUserName");
  const roleEl = document.getElementById("topbarUserRole");
  if (!user) return;
  if (nameEl) nameEl.textContent = user.name || "Commercial Client";
  if (roleEl) roleEl.textContent = user.roleLabel || (user.role === "admin" ? "Lead Hydrogeologist" : "Commercial Client");
}

function bindViewMode() {
  const adminDrawer = document.getElementById("adminLayersDrawer");

  const setMode = (mode) => {
    const isComm = mode === "commercial";
    document.body.classList.toggle("commercial-mode", isComm);
    document.body.classList.toggle("admin-mode", !isComm);

    if (adminDrawer) {
      adminDrawer.hidden = isComm;
    }

    if (isComm) {
      const activeTab = document.querySelector(".tab.active");
      if (activeTab && (activeTab.dataset.tab === "filters" || activeTab.dataset.tab === "scenes" || activeTab.dataset.tab === "model")) {
        const guideTab = document.querySelector('[data-tab="guide"]') || document.querySelector('[data-tab="overview"]');
        if (guideTab) guideTab.click();
      }
    }
  };

  // Sits on window for programmatic role sync
  window.setViewMode = setMode;

  // Initialize according to current auth role
  const user = auth.getUser();
  if (user && user.role === "admin") {
    setMode("admin");
  } else {
    setMode("commercial");
  }
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
  bindRoiCalculator();
  bindViewMode();

  // Initialize Landing Page & Auth system
  initLandingPage((user) => {
    updateUserProfileUi(user);
    if (window.setViewMode) {
      window.setViewMode(user.role === "admin" ? "admin" : "commercial");
    }
    setTimeout(() => mapController?.invalidate(), 150);
  });

  const switchPortalBtn = document.getElementById("switchPortalBtn");
  if (switchPortalBtn) {
    switchPortalBtn.addEventListener("click", () => {
      if (window.showPortalLanding) window.showPortalLanding();
    });
  }

  // Update profile for current session if exists
  if (auth.isAuthenticated()) {
    updateUserProfileUi(auth.getUser());
  }

  // Note: toggles default values come from the HTML `checked` attributes.
  // Do NOT reset them here — mapController reads them on init.

  if (cloudInput) {
    cloudInput.addEventListener("input", () => {
      if (cloudValue) cloudValue.textContent = `${cloudInput.value}%`;
    });
    if (cloudValue) cloudValue.textContent = `${cloudInput.value}%`;
  }

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

  if (potentialInput) {
    potentialInput.addEventListener("input", () => {
      syncPotentialUi(potentialInput.value);
    });
    syncPotentialUi(potentialInput.value);
  }

  document.querySelectorAll(".preset-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const val = Number(pill.dataset.potential);
      syncPotentialUi(val);
      refreshDashboard();
    });
  });

  if (primeToggleBtn) {
    primeToggleBtn.addEventListener("click", () => {
      const current = Number(potentialInput?.value || 0);
      const next = current >= 90 ? 0 : 90;
      syncPotentialUi(next);
      refreshDashboard();
    });
  }

  const debouncedRefresh = debounce(refreshDashboard, 300);
  if (cloudInput) cloudInput.addEventListener("input", debouncedRefresh);
  if (potentialInput) potentialInput.addEventListener("input", debouncedRefresh);

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
    if (retryBtn) retryBtn.addEventListener("click", () => window.location.reload());
    return;
  }

  mapController = createMapController(map, tooltipEl, getToggles(), applyPropertyAnalysisToCalculator, downloadSiteReport);
  mapController.bindToggles();

  const analyzePointBtn = document.getElementById("analyzePointBtn");
  if (analyzePointBtn) {
    analyzePointBtn.addEventListener("click", () => {
      const latVal = parseFloat(document.getElementById("pointLat")?.value) || -21.7439;
      const lonVal = parseFloat(document.getElementById("pointLon")?.value) || 28.0716;
      mapController.analyzePoint(latVal, lonVal, 50.0);
    });
  }

  const sidePanelAnalyzeBtn = document.getElementById("sidePanelAnalyzeBtn");
  if (sidePanelAnalyzeBtn) {
    sidePanelAnalyzeBtn.addEventListener("click", () => {
      const latVal = parseFloat(document.getElementById("pointLat")?.value) || -21.7439;
      const lonVal = parseFloat(document.getElementById("pointLon")?.value) || 28.0716;
      mapController.analyzePoint(latVal, lonVal, 50.0);
    });
  }

  const sidePanelDossierBtn = document.getElementById("sidePanelDossierBtn");
  if (sidePanelDossierBtn) {
    sidePanelDossierBtn.addEventListener("click", () => {
      const latVal = parseFloat(document.getElementById("pointLat")?.value) || -21.7439;
      const lonVal = parseFloat(document.getElementById("pointLon")?.value) || 28.0716;
      mapController.analyzePoint(latVal, lonVal, 50.0);
    });
  }

  if (runBtn) {
    runBtn.addEventListener("click", () => {
      shouldFitBounds = true;
      refreshDashboard();
    });
  }

  ["aoiInput", "seasonInput", "tierInput"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", () => {
        shouldFitBounds = true;
        refreshDashboard();
      });
    }
  });

  refreshDashboard();
  setTimeout(() => mapController.invalidate(), 120);
  window.addEventListener("resize", () => mapController.invalidate());
}

bootstrap();
