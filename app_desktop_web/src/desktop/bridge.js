const DEFAULT_BOOTSTRAP_CONFIG = {
  backendMode: "embedded",
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "starting",
  runtimeWebSocketUrl: "",
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


export function subscribeDesktopBootstrapConfig(listener) {
  const desktopApp = getDesktopApp();
  if (!desktopApp || typeof desktopApp.subscribeBootstrapConfig !== "function") {
    return () => {};
  }
  const unsubscribe = desktopApp.subscribeBootstrapConfig((payload) => {
    listener({
      ...DEFAULT_BOOTSTRAP_CONFIG,
      ...payload,
    });
  });
  listener(getDesktopBootstrapConfig());
  return unsubscribe;
}


export function sendDesktopRendererDiagnostic(payload) {
  const desktopApp = getDesktopApp();
  if (!desktopApp || typeof desktopApp.logRendererDiagnostic !== "function") {
    return false;
  }
  desktopApp.logRendererDiagnostic(payload);
  return true;
}
