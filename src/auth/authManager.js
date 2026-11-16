/**
 * Authentication and Role-based Portal Controller
 * Supports Commercial Client Portal (Farmers, Drillers) and Hydrogeologist Admin Portal.
 */

const STORAGE_KEY = "landsat_water_auth_session";

export const DEFAULT_USERS = {
  client: {
    id: "usr_client_01",
    name: "Kalahari Agri-Holdings",
    role: "client",
    roleLabel: "Commercial Client",
    organization: "Kalahari Cattle & Irrigation Syndicate",
    access: "Commercial Siting, ERT Targets, Yield & TDS, PDF Dossier"
  },
  admin: {
    id: "usr_admin_01",
    name: "Dr. K. Moloi",
    role: "admin",
    roleLabel: "Lead Hydrogeologist",
    organization: "Geological & Water Resource Authority",
    access: "Full Hydrogeology Stack, Diagnostic Layers, ML Calibration, ARSET Benchmarks"
  }
};

class AuthManager {
  constructor() {
    this.session = this.loadSession();
    this.listeners = [];
  }

  loadSession() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        return JSON.parse(data);
      }
    } catch (e) {
      console.warn("Failed to load auth session", e);
    }
    return null;
  }

  saveSession(session) {
    this.session = session;
    try {
      if (session) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (e) {
      console.warn("Failed to save auth session", e);
    }
    this.notify();
  }

  loginAs(roleKey) {
    const user = DEFAULT_USERS[roleKey] || DEFAULT_USERS.client;
    this.saveSession({
      user,
      token: `token_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      loginTime: new Date().toISOString()
    });
    return this.session;
  }

  logout() {
    this.saveSession(null);
  }

  isAuthenticated() {
    return !!this.session && !!this.session.user;
  }

  getUser() {
    return this.session ? this.session.user : null;
  }

  getRole() {
    return this.session && this.session.user ? this.session.user.role : "client";
  }

  isAdmin() {
    return this.getRole() === "admin";
  }

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify() {
    this.listeners.forEach(fn => {
      try {
        fn(this.session);
      } catch (err) {
        console.error("Auth listener error", err);
      }
    });
  }
}

export const auth = new AuthManager();
