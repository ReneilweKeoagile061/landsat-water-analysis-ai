import { AOI_LABELS } from "../config.js";
import { clearElement, el, setMetricValue } from "../utils/dom.js";

export function renderMetrics(metrics, points, scenes, season) {
  const cloudAvg =
    scenes.length > 0 ? scenes.reduce((sum, scene) => sum + scene.cloud, 0) / scenes.length : 0;

  setMetricValue("scenesDiscovered", String(metrics.scenes_discovered));
  setMetricValue("scenesRetained", String(scenes.length));
  setMetricValue("avgCloud", `${cloudAvg.toFixed(1)}%`);
  setMetricValue(
    "waterArea",
    season === "Wet Season"
      ? `${metrics.water_area_wet_km2} km²`
      : `${metrics.water_area_dry_km2} km²`
  );

  const list = document.getElementById("modelMetricsList");
  if (!list) return;

  clearElement(list);
  const entries = [
    ["Held-out accuracy", `${(metrics.model.accuracy * 100).toFixed(2)}%`],
    ["Weighted F1", metrics.model.weighted_f1.toFixed(4)],
    ["Macro F1", metrics.model.macro_f1.toFixed(4)],
    ["Test samples", String(metrics.model.test_samples)],
    ["Map points", String(points.length)],
    ["Filtered scenes", String(scenes.length)],
  ];

  entries.forEach(([label, value]) => {
    const item = el("li");
    item.append(el("strong", null, `${label}: `), document.createTextNode(value));
    list.appendChild(item);
  });

  renderModelValidation(metrics.model);
}

function pct(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function renderModelValidation(model) {
  const chart = document.getElementById("spatialCvChart");
  const finding = document.getElementById("labelAgreementFinding");
  const classList = document.getElementById("perClassMetrics");
  const spatialMean = document.getElementById("spatialCvMean");

  if (spatialMean && model.spatial_cv) {
    spatialMean.textContent = `Mean spatial-block accuracy ${pct(model.spatial_cv.mean)} (labels regenerated without each holdout block).`;
  }

  if (chart && model.spatial_cv?.blocks) {
    clearElement(chart);
    const max = Math.max(...model.spatial_cv.blocks, 0.01);
    model.spatial_cv.blocks.forEach((score, index) => {
      const row = el("div", "cv-bar-row");
      row.appendChild(el("span", "cv-bar-label", `Block ${index + 1}`));
      const track = el("div", "cv-bar-track");
      const fill = el("div", "cv-bar-fill");
      fill.style.width = `${(score / max) * 100}%`;
      track.appendChild(fill);
      row.append(track, el("span", "cv-bar-value", pct(score)));
      chart.appendChild(row);
    });
  }

  if (finding && model.label_agreement) {
    const agree = model.label_agreement.rule_based_vs_kmeans;
    const chance = model.label_agreement.chance_baseline;
    finding.hidden = false;
    clearElement(finding);
    finding.append(
      el("p", "info-label", "Label agreement"),
      el(
        "p",
        "finding-stat",
        `${pct(agree)} K-Means vs independent NDWI/AOI rules`
      ),
      el(
        "p",
        null,
        `That is below the ${pct(chance)} chance baseline. The ${(model.accuracy * 100).toFixed(1)}% classifier score measures how well XGBoost copies K-Means labels, not independent hydrological truth.`
      )
    );
  }

  if (classList && model.per_class) {
    clearElement(classList);
    [
      ["Low", model.per_class.low?.f1],
      ["Medium", model.per_class.medium?.f1],
      ["High", model.per_class.high?.f1],
    ].forEach(([name, f1]) => {
      if (f1 == null) return;
      const item = el("li");
      item.append(el("strong", null, `${name} F1: `), document.createTextNode(f1.toFixed(4)));
      classList.appendChild(item);
    });
  }
}

export function captureCoefficients() {
  return { Low: 0.1, Medium: 0.35, High: 0.65 };
}

export function estimateWaterGain({ hectares, rainfallMm, shares }) {
  const coeffs = captureCoefficients();
  const rainfallM = rainfallMm / 1000;
  const zones = ["Low", "Medium", "High"].map((name) => {
    const areaHa = hectares * (shares[name] / 100);
    const m3 = areaHa * 10000 * rainfallM * coeffs[name];
    return { name, areaHa, coeff: coeffs[name], m3 };
  });
  const totalM3 = zones.reduce((sum, zone) => sum + zone.m3, 0);
  const landingM3 = hectares * 10000 * rainfallM;
  return { zones, totalM3, landingM3 };
}

export function applyPropertyAnalysisToCalculator(analysis) {
  const farmArea = document.getElementById("farmArea");
  const shareLow = document.getElementById("shareLow");
  const shareMedium = document.getElementById("shareMedium");
  const shareHigh = document.getElementById("shareHigh");
  const notice = document.getElementById("drawSyncNotice");

  if (farmArea && analysis.hectares > 0) {
    farmArea.value = analysis.hectares;
  }
  if (shareLow) shareLow.value = analysis.shares.Low;
  if (shareMedium) shareMedium.value = analysis.shares.Medium;
  if (shareHigh) shareHigh.value = analysis.shares.High;

  if (notice) {
    clearElement(notice);
    notice.append(
      el("p", "info-label", "⚡ Farm Boundary Synchronized"),
      el(
        "p",
        null,
        `Imported ${analysis.hectares} ha property (${analysis.shares.High}% High, ${analysis.shares.Medium}% Medium, ${analysis.shares.Low}% Low) from ${analysis.sampleCount} satellite analysis points.`
      )
    );
    notice.hidden = false;
  }

  // Switch to guide tab
  const guideTabBtn = document.getElementById("tab-button-guide") || document.querySelector("[data-tab='guide']");
  guideTabBtn?.click();

  // Trigger form input event to recalculate
  const form = document.getElementById("waterGainForm");
  form?.dispatchEvent(new Event("input", { bubbles: true }));
}

export function bindWaterGainCalculator() {
  const form = document.getElementById("waterGainForm");
  const out = document.getElementById("waterGainResult");
  const printBtn = document.getElementById("printGuideBtn");

  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  if (!form || !out) return;

  const render = () => {
    const hectares = Number(document.getElementById("farmArea").value);
    const rainfallMm = Number(document.getElementById("farmRain").value);
    const shares = {
      Low: Number(document.getElementById("shareLow").value),
      Medium: Number(document.getElementById("shareMedium").value),
      High: Number(document.getElementById("shareHigh").value),
    };
    const shareSum = shares.Low + shares.Medium + shares.High;
    clearElement(out);

    if (!(hectares > 0) || !(rainfallMm > 0)) {
      out.appendChild(el("p", "muted", "Enter area and seasonal rainfall to estimate capture volume."));
      return;
    }
    if (Math.abs(shareSum - 100) > 0.5) {
      out.appendChild(el("p", "muted", `Class shares currently sum to ${shareSum}%. They should total 100.`));
      return;
    }

    const estimate = estimateWaterGain({ hectares, rainfallMm, shares });
    const list = el("ul", "metric-list");
    estimate.zones.forEach((zone) => {
      const item = el("li");
      item.append(
        el("strong", null, `${zone.name}: `),
        document.createTextNode(
          `${zone.areaHa.toFixed(1)} ha × ${(zone.coeff * 100).toFixed(0)}% capture → ${zone.m3.toLocaleString(undefined, { maximumFractionDigits: 0 })} m³`
        )
      );
      list.appendChild(item);
    });
    out.append(
      list,
      el(
        "p",
        null,
        `Total expected yield ${estimate.totalM3.toLocaleString(undefined, { maximumFractionDigits: 0 })} m³ (${(estimate.totalM3 / 1000).toFixed(1)}M litres) of ${estimate.landingM3.toLocaleString(undefined, { maximumFractionDigits: 0 })} m³ rainfall landing on the property.`
      )
    );
  };

  form.addEventListener("input", render);
  render();
}

export function renderTable(scenes) {
  const body = document.getElementById("sceneTableBody");
  if (!body) return;

  clearElement(body);

  if (!scenes.length) {
    const row = el("tr");
    const cell = el("td", null, "No scenes match current filters.");
    cell.colSpan = 5;
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  scenes.forEach((scene) => {
    const row = el("tr");
    const sceneCell = el("td");
    sceneCell.title = scene.scene_id;
    sceneCell.textContent = `${scene.scene_id.slice(0, 22)}…`;
    row.append(
      sceneCell,
      el("td", null, scene.date),
      el("td", null, `${Number(scene.cloud).toFixed(1)}%`),
      el("td", null, scene.season),
      el("td", null, scene.aoi_label)
    );
    body.appendChild(row);
  });

  const count = document.getElementById("sceneCount");
  if (count) count.textContent = `${scenes.length} scene${scenes.length === 1 ? "" : "s"}`;
}

export function renderAoiStats(points) {
  const list = document.getElementById("aoiStats");
  if (!list) return;

  const grouped = points.reduce((acc, feature) => {
    const key = feature.properties.aoi;
    if (!acc[key]) acc[key] = [];
    acc[key].push(feature.properties);
    return acc;
  }, {});

  clearElement(list);
  Object.keys(grouped)
    .sort()
    .forEach((aoi) => {
      const arr = grouped[aoi];
      const avgScore = arr.reduce((sum, item) => sum + Number(item.high_prob || 0), 0) / arr.length;
      const item = el("li");
      item.append(
        el("strong", null, `${AOI_LABELS[aoi] || aoi}`),
        document.createTextNode(` — ${arr.length} points, ${(avgScore * 100).toFixed(1)}% avg high-water`)
      );
      list.appendChild(item);
    });
}

export function renderSubsurfaceSummary(points) {
  const target = document.getElementById("subsurfaceSummary");
  if (!target) return;
  const qualities = points.reduce((counts, feature) => {
    const quality = feature.properties.subsurface_data_quality || "unknown";
    counts[quality] = (counts[quality] || 0) + 1;
    return counts;
  }, {});
  const labels = Object.entries(qualities).map(([quality, count]) => `${quality}: ${count}`);
  target.textContent = points.length
    ? `${points.length} points | ${labels.join(" · ")}. Scores are screening evidence, not drilling guarantees.`
    : "No filtered points contain subsurface evidence.";
}

export function downloadSiteReport(feature) {
  const props = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  const lines = [
    "LandsatWater Site Investigation Report",
    `Coordinates: ${lat.toFixed(5)}, ${lon.toFixed(5)}`,
    `AOI: ${AOI_LABELS[props.aoi] || props.aoi}`,
    `Surface potential: ${props.predicted_label} (${(Number(props.high_prob || 0) * 100).toFixed(1)}%)`,
    `Estimated DTWT: ${props.depth_to_water_table_m ?? "N/A"} m (${props.dtwt_class || "N/A"})`,
    `Drill depth range: ${props.drill_depth_min_m ?? "N/A"}-${props.drill_depth_max_m ?? "N/A"} m`,
    `Aquifer yield estimate: ${props.aquifer_productivity_ls ?? "N/A"} L/s`,
    `Borehole feasibility: ${props.borehole_feasibility_score != null ? `${(Number(props.borehole_feasibility_score) * 100).toFixed(0)}%` : "N/A"}`,
    `Phreatophyte index: ${props.phreatophyte_index != null ? `${(Number(props.phreatophyte_index) * 100).toFixed(0)}%` : "N/A"}`,
    `Infiltration: ${props.infiltration_score ?? "N/A"}% (${props.infiltration_class || "N/A"})`,
    `Evidence: ${props.subsurface_data_source || "Unverified"} / ${props.subsurface_data_quality || "unknown"}`,
    `Recommended next step: ${props.validation_next_step || "Collect field measurements before drilling"}`,
    "",
    "This report is a screening aid. Confirm groundwater conditions with qualified hydrogeological and geophysical surveys.",
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `landsatwater-site-${lat.toFixed(4)}-${lon.toFixed(4)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

export function renderError(message) {
  const list = document.getElementById("modelMetricsList");
  if (!list) return;
  clearElement(list);
  list.appendChild(el("li", null, message));
  const retryBtn = document.getElementById("retryBtn");
  if (retryBtn) retryBtn.hidden = false;
}
