export function clearElement(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function appendTooltipContent(container, { title, lines, badgeText, badgeClass }) {
  clearElement(container);
  container.appendChild(el("h4", null, title));
  lines.forEach(({ label, value }) => {
    const paragraph = el("p");
    paragraph.append(document.createTextNode(`${label}: `));
    const strong = el("strong", null, value);
    paragraph.append(strong);
    container.appendChild(paragraph);
  });
  if (badgeText) {
    container.appendChild(el("span", `tooltip-badge ${badgeClass}`, badgeText));
  }
}

export function setMetricValue(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

export function setLoadingState(isLoading) {
  const overlay = document.getElementById("loadingOverlay");
  const dashboard = document.querySelector(".dashboard");
  if (overlay) overlay.hidden = !isLoading;
  if (dashboard) dashboard.setAttribute("aria-busy", String(isLoading));
}

export function renderLoadStatus(errors) {
  const banner = document.getElementById("statusBanner");
  if (!banner) return;

  const messages = Object.entries(errors);
  if (!messages.length) {
    banner.hidden = true;
    clearElement(banner);
    return;
  }

  banner.hidden = false;
  clearElement(banner);
  messages.forEach(([name, message]) => {
    banner.appendChild(el("p", "status-line", `Failed to load ${name}: ${message}`));
  });
}
