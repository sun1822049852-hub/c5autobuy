const DEFAULT_BOOTSTRAP_CONFIG = {
  backendMode: "embedded",
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "starting",
  runtimeWebSocketUrl: "",
};


function getDesktopApp() {
  return globalThis.window?.desktopApp ?? null;
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


export function subscribeDesktopBootstrapConfig(listener) {
  const desktopApp = getDesktopApp();
  if (typeof listener !== "function") {
    return () => {};
  }

  if (!desktopApp) {
    queueTask(() => {
      listener(getDefaultDesktopBootstrapConfig());
    });
    return () => {};
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
