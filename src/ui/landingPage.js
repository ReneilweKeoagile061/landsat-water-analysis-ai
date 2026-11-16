/**
 * Landing Page & Authentication Portal Controller
 * Petrol Blue & Bone White aesthetic with Bone Yellow accents.
 */

import { auth, DEFAULT_USERS } from "../auth/authManager.js";
import { icons } from "./icons.js";

export function initLandingPage(onLoginSuccess) {
  const overlay = document.getElementById("portalLandingOverlay");
  if (!overlay) return;

  const renderLanding = () => {
    overlay.innerHTML = `
      <div class="landing-container">
        <!-- Navigation Header -->
        <header class="landing-nav">
          <div class="landing-brand">
            <div class="landing-logo-emblem">
              <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="#153b51"/>
                <path d="M16 6 L23 17 C23 21 19.9 24 16 24 C12.1 24 9 21 9 17 Z" fill="#d89f38"/>
                <circle cx="16" cy="17" r="2.5" fill="#faf8f5"/>
              </svg>
            </div>
            <div>
              <span class="landing-brand-title">Landsat<span class="highlight">Water</span></span>
              <span class="landing-brand-sub">Commercial Groundwater Intelligence</span>
            </div>
          </div>
          <div class="landing-nav-actions">
            <span class="portal-badge-pill">Transboundary STAS / Karoo Calibrated</span>
          </div>
        </header>

        <!-- Hero Section -->
        <main class="landing-main">
          <div class="landing-hero">
            <div class="hero-eyebrow">
              <span class="accent-dot"></span>
              TWO-STAGE SATELLITE ML &amp; STRUCTURAL LINEAMENT SITING
            </div>
            <h1 class="hero-heading">
              Precision Borehole Siting Before You Mobilize a Rig
            </h1>
            <p class="hero-description">
              Reduce costly dry-hole risks across Southern Africa. Our platform evaluates multi-spectral Landsat 8/9 imagery, Sentinel-1 SAR lineaments, and hydrogeological fractures against 6,266 ground-truth boreholes to deliver top 3 drill targets and 200m ERT geophysics survey lines.
            </p>

            <div class="hero-metrics-grid">
              <div class="hero-metric-card">
                <div class="metric-val">84.2%</div>
                <div class="metric-lbl">Model Strike Accuracy</div>
                <div class="metric-sub">Calibrated on verified BGI &amp; STAS wells</div>
              </div>
              <div class="hero-metric-card">
                <div class="metric-val">200m</div>
                <div class="metric-lbl">ERT Geophysics Transects</div>
                <div class="metric-sub">Calculated orthogonal to structural fractures</div>
              </div>
              <div class="hero-metric-card">
                <div class="metric-val">50 km</div>
                <div class="metric-lbl">Analysis Radius</div>
                <div class="metric-sub">Single-click farm point or boundary polygon</div>
              </div>
            </div>
          </div>

          <!-- Dual Portal Login Cards -->
          <div class="portal-login-section">
            <h2 class="portal-section-title">Select Portal Gateway</h2>
            <div class="portal-cards-grid">
              
              <!-- Card 1: Commercial Client Portal -->
              <div class="portal-card client-portal-card">
                <div class="portal-card-header">
                  <div class="portal-card-icon client-icon">
                    ${icons.user}
                  </div>
                  <div>
                    <h3 class="portal-card-title">Commercial Client Portal</h3>
                    <p class="portal-card-role">Farm Owners, Agricultural Syndicates &amp; Drillers</p>
                  </div>
                </div>
                <ul class="portal-feature-list">
                  <li>${icons.check} <span>Instant GPS Point (50 km) &amp; Farm Boundary Siting</span></li>
                  <li>${icons.check} <span>Top 3 Ranked Drill Targets with Coordinates</span></li>
                  <li>${icons.check} <span>Predicted Yield Tier (Commercial High, Medium, Dry Risk)</span></li>
                  <li>${icons.check} <span>Drilling Depth &amp; Estimated TDS Salinity</span></li>
                  <li>${icons.check} <span>1-Click Print &amp; PDF Drilling Dossier Export</span></li>
                </ul>
                <div class="portal-action-box">
                  <button id="loginClientBtn" class="primary-btn portal-btn full-width" type="button">
                    Enter as Commercial Client &rarr;
                  </button>
                  <p class="portal-demo-note">Quick Launch: Kalahari Agri-Holdings</p>
                </div>
              </div>

              <!-- Card 2: Hydrogeologist Admin Portal -->
              <div class="portal-card admin-portal-card">
                <div class="portal-card-header">
                  <div class="portal-card-icon admin-icon">
                    ${icons.shield}
                  </div>
                  <div>
                    <h3 class="portal-card-title">Hydrogeologist Admin Portal</h3>
                    <p class="portal-card-role">Exploration Geologists &amp; Hydrology Researchers</p>
                  </div>
                </div>
                <ul class="portal-feature-list">
                  <li>${icons.check} <span>Full 9-Layer Diagnostic Sensor Telemetry</span></li>
                  <li>${icons.check} <span>Surface Moisture (NDWI) &amp; Open Water (MNDWI)</span></li>
                  <li>${icons.check} <span>Sentinel-1 SAR Fracture Lineaments &amp; DEM Slope</span></li>
                  <li>${icons.check} <span>NASA ARSET Empirical Validation &amp; Spatial Benchmarks</span></li>
                  <li>${icons.check} <span>Raw Landsat 8/9 Scene Filtering &amp; Model Metadata</span></li>
                </ul>
                <div class="portal-action-box">
                  <button id="loginAdminBtn" class="primary-btn portal-btn admin-btn full-width" type="button">
                    Enter as Lead Hydrogeologist &rarr;
                  </button>
                  <p class="portal-demo-note">Quick Launch: Dr. K. Moloi (Admin Access)</p>
                </div>
              </div>

            </div>

            <!-- Custom Sign In Accordion / Fallback -->
            <div class="custom-signin-box">
              <details class="custom-signin-drawer">
                <summary>Looking to sign in with specific corporate credentials?</summary>
                <form id="customLoginForm" class="custom-login-form">
                  <div class="form-row">
                    <label>
                      Work Email
                      <input id="loginEmail" type="email" placeholder="geologist@enterprise.com" required value="client@kalahari-agri.com" />
                    </label>
                    <label>
                      Account Role
                      <select id="loginRoleSelect">
                        <option value="client">Commercial Client (Farmer / Driller)</option>
                        <option value="admin">System Hydrogeologist (Admin)</option>
                      </select>
                    </label>
                  </div>
                  <button class="primary-btn" type="submit">Sign In with Credentials</button>
                </form>
              </details>
            </div>
          </div>
        </main>

        <!-- Footer -->
        <footer class="landing-footer">
          <p>LandsatWater &copy; ${new Date().getFullYear()} &middot; Calibration Calibrated on 6,266 Verified Transboundary Boreholes &middot; Republic of Botswana, Namibia &amp; South Africa</p>
        </footer>
      </div>
    `;

    // Bind login buttons
    const clientBtn = document.getElementById("loginClientBtn");
    const adminBtn = document.getElementById("loginAdminBtn");
    const customForm = document.getElementById("customLoginForm");

    if (clientBtn) {
      clientBtn.addEventListener("click", () => {
        auth.loginAs("client");
        hideLanding();
      });
    }

    if (adminBtn) {
      adminBtn.addEventListener("click", () => {
        auth.loginAs("admin");
        hideLanding();
      });
    }

    if (customForm) {
      customForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const role = document.getElementById("loginRoleSelect")?.value || "client";
        auth.loginAs(role);
        hideLanding();
      });
    }
  };

  const showLanding = () => {
    overlay.hidden = false;
    overlay.classList.add("visible");
    renderLanding();
  };

  const hideLanding = () => {
    overlay.classList.remove("visible");
    setTimeout(() => {
      overlay.hidden = true;
      if (typeof onLoginSuccess === "function") {
        onLoginSuccess(auth.getUser());
      }
    }, 200);
  };

  // Expose methods
  window.showPortalLanding = showLanding;
  window.hidePortalLanding = hideLanding;

  // Initial check
  if (!auth.isAuthenticated()) {
    showLanding();
  } else {
    overlay.hidden = true;
    if (typeof onLoginSuccess === "function") {
      onLoginSuccess(auth.getUser());
    }
  }

  // Subscribe to auth changes
  auth.subscribe((session) => {
    if (!session) {
      showLanding();
    }
  });
}
