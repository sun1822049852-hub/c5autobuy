const DEFAULT_BOOTSTRAP_CONFIG = {
  backendMode: "embedded",
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "starting",
  runtimeWebSocketUrl: "",
  pageWarmupEnabled: false,
};
const BROWSER_BOOTSTRAP_HEALTH_POLL_MS = 1000;


function getDesktopApp() {
  return globalThis.window?.desktopApp ?? null;
}

function resolveBootstrapFetch() {
  return globalThis.window?.fetch ?? globalThis.fetch;
}

function buildEmbeddedHealthUrl(apiBaseUrl) {
  try {
    const url = new URL(String(apiBaseUrl || DEFAULT_BOOTSTRAP_CONFIG.apiBaseUrl));
    url.pathname = "/health";
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return "";
  }
}

function normalizeBootstrapConfig(payload) {
  return {
    ...DEFAULT_BOOTSTRAP_CONFIG,
    ...(payload ?? {}),
  };
}

function queueTask(task) {
  if (typeof globalThis.setTimeout === "function") {
    globalThis.setTimeout(task, 0);
    return;
  }
  Promise.resolve().then(task);
}

export function getDefaultDesktopBootstrapConfig() {
  return {
    ...DEFAULT_BOOTSTRAP_CONFIG,
  };
}


export function getDesktopBootstrapConfig() {
  const desktopApp = getDesktopApp();

  if (!desktopApp || typeof desktopApp.getBootstrapConfig !== "function") {
    return getDefaultDesktopBootstrapConfig();
  }

  return normalizeBootstrapConfig(desktopApp.getBootstrapConfig());
}

async function probeBrowserEmbeddedBootstrapConfig(baseConfig) {
  const fetchImpl = resolveBootstrapFetch();
  const healthUrl = buildEmbeddedHealthUrl(baseConfig.apiBaseUrl);

  if (typeof fetchImpl !== "function" || !healthUrl) {
    return baseConfig;
  }

  try {
    const response = await fetchImpl(healthUrl, {
      headers: {
        Accept: "application/json",
      },
      method: "GET",
    });

    if (!response?.ok) {
      return baseConfig;
    }

    const payload = typeof response.json === "function"
      ? await response.json().catch(() => null)
      : null;

    if (payload?.ready === true) {
      return normalizeBootstrapConfig({
        ...baseConfig,
        backendStatus: "ready",
      });
    }
  } catch {
    return baseConfig;
  }

  return baseConfig;
}

function subscribeBrowserBootstrapConfig(listener) {
  const baseConfig = getDefaultDesktopBootstrapConfig();
  let disposed = false;
  let timeoutId = null;

  const emit = (payload) => {
    if (disposed) {
      return;
    }
    listener(normalizeBootstrapConfig(payload));
  };

  const scheduleNextProbe = () => {
    if (disposed) {
      return;
    }
    timeoutId = globalThis.setTimeout(() => {
      timeoutId = null;
      void probeAndEmit();
    }, BROWSER_BOOTSTRAP_HEALTH_POLL_MS);
  };

  const probeAndEmit = async () => {
    const nextConfig = await probeBrowserEmbeddedBootstrapConfig(baseConfig);
    emit(nextConfig);
    if (nextConfig.backendStatus !== "ready") {
      scheduleNextProbe();
    }
  };

  queueTask(() => {
    emit(baseConfig);
    void probeAndEmit();
  });

  return () => {
    disposed = true;
    if (timeoutId !== null && typeof globalThis.clearTimeout === "function") {
      globalThis.clearTimeout(timeoutId);
    }
  };
}


export function subscribeDesktopBootstrapConfig(listener) {
  const desktopApp = getDesktopApp();
  if (typeof listener !== "function") {
    return () => {};
  }

  if (!desktopApp) {
    return subscribeBrowserBootstrapConfig(listener);
  }

  const emit = (payload) => {
    listener(normalizeBootstrapConfig(payload));
  };

  let unsubscribe = () => {};
  if (typeof desktopApp.subscribeBootstrapConfig === "function") {
    unsubscribe = desktopApp.subscribeBootstrapConfig((payload) => {
      emit(payload);
    });
  }

  queueTask(() => {
    if (typeof desktopApp.requestBootstrapConfig === "function") {
      Promise.resolve(desktopApp.requestBootstrapConfig())
        .then((payload) => {
          emit(payload);
        })
        .catch(() => {});
      return;
    }

    if (typeof desktopApp.subscribeBootstrapConfig !== "function") {
      if (typeof desktopApp.getBootstrapConfig === "function") {
        emit(desktopApp.getBootstrapConfig());
        return;
      }
      emit(getDefaultDesktopBootstrapConfig());
    }
  });

  return typeof unsubscribe === "function" ? unsubscribe : () => {};
}


export function sendDesktopRendererDiagnostic(payload) {
  const desktopApp = getDesktopApp();
  if (!desktopApp || typeof desktopApp.logRendererDiagnostic !== "function") {
    return false;
  }
  desktopApp.logRendererDiagnostic(payload);
  return true;
}
