import { AOI_LABELS } from "../config.js";
import { clearElement, el, setMetricValue } from "../utils/dom.js";

export function renderMetrics(metrics, points, scenes, season) {
  const cloudAvg =
    scenes.length > 0  scenes.reduce((sum, scene) => sum + scene.cloud, 0) / scenes.length : 0;

  setMetricValue("scenesDiscovered", String(metrics.scenes_discovered));
  setMetricValue("scenesRetained", String(scenes.length));
  setMetricValue("avgCloud", `${cloudAvg.toFixed(1)}%`);
  setMetricValue(
    "waterArea",
    season === "Wet Season"
       `${metrics.water_area_wet_km2} km²`
      : `${metrics.water_area_dry_km2} km²`
  );

  const list = document.getElementById("modelMetricsList");
  if (!list) return;

  clearElement(list);
  const entries = [
    [
      metrics.model.accuracy_name || "Model Self-Consistency Score",
      `${(metrics.model.accuracy * 100).toFixed(2)}%`,
    ],
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

  if (chart && model.spatial_cv.blocks) {
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
        `That is below the ${pct(chance)} chance baseline. The ${(model.accuracy * 100).toFixed(1)}% figure is a Model Self-Consistency Score: XGBoost copying K-Means labels, not independent borehole skill.`
      )
    );
  }

  if (classList && model.per_class) {
    clearElement(classList);
    [
      ["Low", model.per_class.low.f1],
      ["Medium", model.per_class.medium.f1],
      ["High", model.per_class.high.f1],
    ].forEach(([name, f1]) => {
      if (f1 == null) return;
      const item = el("li");
      item.append(el("strong", null, `${name} F1: `), document.createTextNode(f1.toFixed(4)));
      classList.appendChild(item);
    });
  }

  renderNasaArsetCard(model);
}

function renderNasaArsetCard() {
  const card = document.getElementById("nasaArsetCard");
  if (!card) return;
  card.hidden = false;
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
      el("p", "info-label", " Farm Boundary Synchronized"),
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
  guideTabBtn.click();

  // Trigger form input event to recalculate
  const form = document.getElementById("waterGainForm");
  form.dispatchEvent(new Event("input", { bubbles: true }));
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

  const renderBoreholeYield = () => {
    const depth = Number(document.getElementById("boreholeDepthInput").value);
    const prod = Number(document.getElementById("boreholeProdInput").value);
    const hours = Number(document.getElementById("boreholeHoursInput").value);
    const outYield = document.getElementById("boreholeYieldResult");

    if (!outYield) return;
    clearElement(outYield);

    if (!(depth > 0) || !(prod > 0) || !(hours > 0)) {
      outYield.appendChild(el("p", "muted", "Enter depth, yield, and pumping hours to estimate capacity."));
      return;
    }

    const daily_m3 = (prod * hours * 3600) / 1000;
    const cattleSupported = Math.floor(daily_m3 / 0.05);
    const irrigationHa = (daily_m3 / 6).toFixed(1);

    const list = el("ul", "metric-list");
    const item1 = el("li");
    item1.append(el("strong", null, "Daily Yield: "), document.createTextNode(`${daily_m3.toLocaleString(undefined, { maximumFractionDigits: 0 })} m³/day`));
    const item2 = el("li");
    item2.append(el("strong", null, "Livestock Capacity: "), document.createTextNode(`~${cattleSupported.toLocaleString()} cattle (50L/head/day)`));
    const item3 = el("li");
    item3.append(el("strong", null, "Irrigation Capacity: "), document.createTextNode(`~${irrigationHa} ha (60m³/ha/day drip)`));

    list.append(item1, item2, item3);
    outYield.appendChild(list);
  };

  const depthInput = document.getElementById("boreholeDepthInput");
  const prodInput = document.getElementById("boreholeProdInput");
  const hoursInput = document.getElementById("boreholeHoursInput");

  if (depthInput && prodInput && hoursInput) {
    depthInput.addEventListener("input", renderBoreholeYield);
    prodInput.addEventListener("input", renderBoreholeYield);
    hoursInput.addEventListener("input", renderBoreholeYield);
    renderBoreholeYield();
  }
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
  if (count) count.textContent = `${scenes.length} scene${scenes.length === 1  "" : "s"}`;
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
     `${points.length} points | ${labels.join(" · ")}. Scores are screening evidence, not drilling guarantees.`
    : "No filtered points contain subsurface evidence.";
}

export function computeVesCableTable(targetDepthM) {
  const depth = targetDepthM && targetDepthM > 0  targetDepthM : 50;
  const abMin = Math.max(3.0 * depth, depth / 0.19);
  const steps = [];
  for (let i = 1; i <= 8; i++) {
    const ab = abMin * (i / 8);
    const mn = ab / 5.0;
    const s = ab / 2.0;
    const b = mn / 2.0;
    const k = (Math.PI * (s * s - b * b)) / (2.0 * b);
    const ze = 0.19 * ab;
    steps.push({
      step: i,
      ab_m: ab.toFixed(1),
      mn_m: mn.toFixed(1),
      k_factor: Math.round(k),
      ze_depth_m: ze.toFixed(1),
    });
  }
  return { abMin: abMin.toFixed(0), mnMax: (abMin / 5).toFixed(0), steps };
}

export function openPdfDossierModal(feature) {
  const modal = document.getElementById("dossierModal");
  const area = document.getElementById("dossierPrintArea");
  if (!modal || !area) return;

  const props = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  const targetDepth = Number(props.depth_to_water_table_m || 50);
  const ves = computeVesCableTable(targetDepth);
  const isClayHazard = (props.clay_fraction_pct != null && Number(props.clay_fraction_pct) > 35) || props.clay_shielding_hazard;

  clearElement(area);
  area.innerHTML = `
    <div class="pdf-dossier-document">
      <div class="pdf-header">
        <div class="pdf-brand">
          <h2>LANDSAT &amp; AGRIPULSE</h2>
          <p>Groundwater Intelligence &amp; Geophysical Siting Dossier</p>
        </div>
        <div class="pdf-stamp">
          <span>OFFICIAL SCREENING BRIEF</span>
          <small>Botswana Hydrogeology Survey</small>
        </div>
      </div>

      <div class="pdf-meta-bar">
        <div><strong>GPS Coordinates:</strong> ${lat.toFixed(5)}°, ${lon.toFixed(5)}°</div>
        <div><strong>AOI Region:</strong> ${AOI_LABELS[props.aoi] || props.aoi}</div>
        <div><strong>Surface Potential:</strong> <span class="tag ${props.predicted_label.toLowerCase()}">${props.predicted_label} (${(Number(props.high_prob || 0) * 100).toFixed(1)}%)</span></div>
      </div>

      <div class="pdf-section">
        <h4 class="pdf-section-title">1. Subsurface Hydrogeological Parameters</h4>
        <div class="pdf-grid-4">
          <div class="pdf-metric-box">
            <span>Depth to Water Table</span>
            <strong>~${Number(props.depth_to_water_table_m || 50).toFixed(0)} m</strong>
            <small>${props.dtwt_class || "Moderate (25-75 m)"}</small>
          </div>
          <div class="pdf-metric-box">
            <span>Recommended Drill Depth</span>
            <strong>${props.drill_depth_min_m || Math.round(targetDepth + 15)}–${props.drill_depth_max_m || Math.round(targetDepth + 40)} m</strong>
            <small>Target Aquifer Zone</small>
          </div>
          <div class="pdf-metric-box">
            <span>Estimated Aquifer Yield</span>
            <strong>${Number(props.aquifer_productivity_ls || 3.0).toFixed(1)} L/s</strong>
            <small>${props.aquifer_type || "Karoo / Sedimentary"}</small>
          </div>
          <div class="pdf-metric-box">
            <span>Borehole Feasibility</span>
            <strong>${(Number(props.borehole_feasibility_score || 0.65) * 100).toFixed(0)}%</strong>
            <small>Recharge Probability</small>
          </div>
        </div>
      </div>

      <div class="pdf-section">
        <h4 class="pdf-section-title">2. Soil &amp; Recharge Risk Assessment</h4>
        <div class="pdf-risk-card ${isClayHazard  'hazard' : 'safe'}">
          ${isClayHazard 
             '<strong>️ Conductive Clay Shielding Hazard (&lt;10 Ω·m):</strong> SoilGrids clay &gt;35% detected. Heavy clay seals inhibit deep aquifer recharge. <em>Recommended Action: Lined surface rainwater harvesting (earth dams or ponds) over deep borehole drilling.</em>'
            : '<strong> Low Clay Shielding Risk:</strong> Soil clay fraction (' + (Number(props.clay_fraction_pct || 22).toFixed(0)) + '%) allows permeable rainwater infiltration and fracture recharge.'
          }
        </div>
      </div>

      <div class="pdf-section">
        <h4 class="pdf-section-title">3. Schlumberger VES Field Geophysics Survey Layout (Andreas de Jong Standard)</h4>
        <p class="pdf-subtext">Array geometry: Current cable spread <strong>AB ≥ ${ves.abMin} m</strong> (Rule: AB ≥ 3× depth, Ze = 0.19× AB), Potential cable <strong>MN ≤ ${ves.mnMax} m</strong> (AB ≥ 5× MN).</p>
        <table class="pdf-table">
          <thead>
            <tr>
              <th>Expansion Step</th>
              <th>Current Spread AB (m)</th>
              <th>Potential Spacing MN (m)</th>
              <th>Geometric Factor (K)</th>
              <th>Investigation Depth Ze (m)</th>
            </tr>
          </thead>
          <tbody>
            ${ves.steps.map(s => `
              <tr>
                <td>Step ${s.step}</td>
                <td><strong>${s.ab_m} m</strong></td>
                <td>${s.mn_m} m</td>
                <td>${s.k_factor.toLocaleString()}</td>
                <td>~${s.ze_depth_m} m</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <div class="pdf-section pdf-compliance-box">
        <h4 class="pdf-section-title">4. Hydrogeological Standard Compliance &amp; Field Clearance Notice</h4>
        <ul class="pdf-compliance-list">
          <li><strong>NASA ARSET Baseline:</strong> Satellite multispectral data provides 36% basin-scale correlation vs 10% point-scale correlation. Confidence is designated as 0.45 preliminary screening.</li>
          <li><strong>Andreas de Jong VES Protocol:</strong> Current cable length AB ≥ 3× target borehole depth is mandatory prior to rig mobilization.</li>
          <li><strong>Target Storage Conversion:</strong> Volumetric water storage ΔGW = dh × S (0.15 for Kalahari unconfined sands, 0.0001 for Karoo/Basement bedrock).</li>
        </ul>
        <p class="pdf-footer-note">This dossier is an AI-assisted screening assessment. On-site geophysical resistivity profiling and hydrogeological clearance must be completed before drilling operations begin.</p>
      </div>
    </div>
  `;

  modal.hidden = false;

  const printBtn = document.getElementById("printDossierModalBtn");
  const closeBtn = document.getElementById("closeDossierModalBtn");

  if (printBtn) {
    printBtn.onclick = () => window.print();
  }
  if (closeBtn) {
    closeBtn.onclick = () => { modal.hidden = true; };
  }
}

export function downloadSiteReport(feature) {
  openPdfDossierModal(feature);
}

export function renderError(message) {
  const list = document.getElementById("modelMetricsList");
  if (!list) return;
  clearElement(list);
  list.appendChild(el("li", null, message));
  const retryBtn = document.getElementById("retryBtn");
  if (retryBtn) retryBtn.hidden = false;
}

