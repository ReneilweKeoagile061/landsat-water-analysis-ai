export function filterPoints(points, filters) {
  return points.filter((feature) => {
    const props = feature.properties;
    if (filters.aoi !== "ALL" && props.aoi !== filters.aoi) return false;
    if (props.season && props.season !== filters.season) return false;
    if (props.tier && props.tier !== filters.tier) return false;
    return true;
  });
}

export function filterScenes(scenes, filters) {
  return scenes.filter((scene) => {
    if (scene.cloud > filters.cloud) return false;
    if (scene.tier !== filters.tier) return false;
    if (scene.season !== filters.season) return false;
    if (filters.aoi !== "ALL" && scene.aoi !== filters.aoi) return false;
    return true;
  });
}

export function readFiltersFromDom() {
  return {
    aoi: document.getElementById("aoiInput")?.value ?? "ALL",
    cloud: Number(document.getElementById("cloudInput")?.value ?? 20),
    season: document.getElementById("seasonInput")?.value ?? "Wet Season",
    tier: document.getElementById("tierInput")?.value ?? "Tier 1",
  };
}
