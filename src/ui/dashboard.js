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
    ["Accuracy", `${(metrics.model.accuracy * 100).toFixed(2)}%`],
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

export function renderError(message) {
  const list = document.getElementById("modelMetricsList");
  if (!list) return;
  clearElement(list);
  list.appendChild(el("li", null, message));
  const retryBtn = document.getElementById("retryBtn");
  if (retryBtn) retryBtn.hidden = false;
}
