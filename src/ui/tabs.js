export function bindTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");

  const activate = (tab) => {
    tabs.forEach((node) => {
      const isActive = node === tab;
      node.classList.toggle("active", isActive);
      node.setAttribute("aria-selected", String(isActive));
      node.tabIndex = isActive ? 0 : -1;
    });

    panels.forEach((panel) => {
      panel.classList.remove("active");
      panel.hidden = true;
    });
    const panel = document.getElementById(`tab-${tab.dataset.tab}`);
    if (panel) {
      panel.classList.add("active");
      panel.hidden = false;
      tab.setAttribute("aria-controls", panel.id);
    }
  };

  tabs.forEach((tab, index) => {
    tab.setAttribute("role", "tab");
    tab.id = `tab-button-${tab.dataset.tab}`;
    tab.setAttribute("aria-selected", tab.classList.contains("active") ? "true" : "false");
    tab.tabIndex = tab.classList.contains("active") ? 0 : -1;

    const panel = document.getElementById(`tab-${tab.dataset.tab}`);
    if (panel) {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tab.id);
      tab.setAttribute("aria-controls", panel.id);
    }

    tab.addEventListener("click", () => activate(tab));

    if (tab.classList.contains("active")) {
      const panel = document.getElementById(`tab-${tab.dataset.tab}`);
      if (panel) panel.hidden = false;
    }
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const lastIndex = tabs.length - 1;
      let next = index;
      if (event.key === "ArrowRight") next = index === lastIndex ? 0 : index + 1;
      if (event.key === "ArrowLeft") next = index === 0 ? lastIndex : index - 1;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = lastIndex;
      tabs[next].focus();
      activate(tabs[next]);
    });
  });
}

export function bindPanelToggle() {
  const toggle = document.getElementById("panelToggle");
  const panel = document.querySelector(".side-panel");
  if (!toggle || !panel) return;

  toggle.addEventListener("click", () => {
    const collapsed = panel.classList.toggle("collapsed");
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.textContent = collapsed ? "Show panel" : "Hide panel";
  });
}
