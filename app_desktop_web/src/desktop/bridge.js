const DEFAULT_BOOTSTRAP_CONFIG = {
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "unknown",
};


export function getDesktopBootstrapConfig() {
  const desktopApp = globalThis.window?.desktopApp;

  if (!desktopApp || typeof desktopApp.getBootstrapConfig !== "function") {
    return DEFAULT_BOOTSTRAP_CONFIG;
  }

  return {
    ...DEFAULT_BOOTSTRAP_CONFIG,
    ...desktopApp.getBootstrapConfig(),
  };
}
