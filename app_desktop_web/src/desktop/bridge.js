const DEFAULT_BOOTSTRAP_CONFIG = {
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "unknown",
};


function getDesktopApp() {
  return globalThis.window?.desktopApp ?? null;
}


export function getDesktopBootstrapConfig() {
  const desktopApp = getDesktopApp();

  if (!desktopApp || typeof desktopApp.getBootstrapConfig !== "function") {
    return DEFAULT_BOOTSTRAP_CONFIG;
  }

  return {
    ...DEFAULT_BOOTSTRAP_CONFIG,
    ...desktopApp.getBootstrapConfig(),
  };
}


export function sendDesktopRendererDiagnostic(payload) {
  const desktopApp = getDesktopApp();
  if (!desktopApp || typeof desktopApp.logRendererDiagnostic !== "function") {
    return false;
  }
  desktopApp.logRendererDiagnostic(payload);
  return true;
}
