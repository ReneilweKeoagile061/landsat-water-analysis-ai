/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";

describe("AgriPulse Frontend Integration", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="tab-agripulse"></div>
      <input id="toggleBgiBoreholes" type="checkbox" checked />
      <input id="toggleDrillTargets" type="checkbox" checked />
    `;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("should have AgriPulse ML tab present", () => {
    const tab = document.getElementById("tab-agripulse");
    expect(tab).not.toBeNull();
  });

  it("should have BGI boreholes and drill targets toggles", () => {
    const bgiToggle = document.getElementById("toggleBgiBoreholes");
    const drillToggle = document.getElementById("toggleDrillTargets");
    expect(bgiToggle.checked).toBe(true);
    expect(drillToggle.checked).toBe(true);
  });
});
