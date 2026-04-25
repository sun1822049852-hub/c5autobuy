const { contextBridge, ipcRenderer } = require("electron");


const DEFAULT_BOOTSTRAP_CONFIG = {
  backendMode: "embedded",
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "starting",
  runtimeWebSocketUrl: "",
  pageWarmupEnabled: false,
};
const BOOTSTRAP_UPDATED_CHANNEL = "desktop:bootstrap-config-updated";
const BOOTSTRAP_REQUEST_CHANNEL = "desktop:request-bootstrap-config";
let bootstrapConfigSnapshot = {
  ...DEFAULT_BOOTSTRAP_CONFIG,
};
let bootstrapRefreshPromise = null;
const bootstrapListeners = new Set();

function normalizeBootstrapConfig(payload) {
  return {
    ...DEFAULT_BOOTSTRAP_CONFIG,
    ...(payload ?? {}),
  };
}

function emitBootstrapSnapshotToListeners() {
  const payload = {
    ...bootstrapConfigSnapshot,
  };
  for (const listener of bootstrapListeners) {
    try {
      listener(payload);
    } catch {
      // ignore listener errors to avoid breaking other subscribers
    }
  }
}

function updateBootstrapSnapshot(payload) {
  bootstrapConfigSnapshot = normalizeBootstrapConfig(payload);
  emitBootstrapSnapshotToListeners();
}

function requestBootstrapSnapshotRefresh() {
  if (bootstrapRefreshPromise) {
    return bootstrapRefreshPromise;
  }

  bootstrapRefreshPromise = Promise.resolve()
    .then(() => ipcRenderer.invoke(BOOTSTRAP_REQUEST_CHANNEL))
    .then((payload) => {
      updateBootstrapSnapshot(payload);
      return {
        ...bootstrapConfigSnapshot,
      };
    })
    .catch(() => ({
      ...bootstrapConfigSnapshot,
    }))
    .finally(() => {
      bootstrapRefreshPromise = null;
    });

  return bootstrapRefreshPromise;
}

function scheduleBootstrapSnapshotRefresh() {
  setTimeout(() => {
    requestBootstrapSnapshotRefresh().catch(() => {
      // keep local defaults when sync snapshot is unavailable
    });
  }, 0);
}

ipcRenderer.on(BOOTSTRAP_UPDATED_CHANNEL, (_event, payload) => {
  updateBootstrapSnapshot(payload);
});
scheduleBootstrapSnapshotRefresh();


contextBridge.exposeInMainWorld("desktopApp", {
  getBootstrapConfig() {
    return {
      ...bootstrapConfigSnapshot,
    };
  },
  requestBootstrapConfig() {
    return requestBootstrapSnapshotRefresh();
  },
  subscribeBootstrapConfig(listener) {
    if (typeof listener !== "function") {
      return () => {};
    }
    bootstrapListeners.add(listener);
    setTimeout(() => {
      if (!bootstrapListeners.has(listener)) {
        return;
      }
      listener({
        ...bootstrapConfigSnapshot,
      });
    }, 0);
    return () => {
      bootstrapListeners.delete(listener);
    };
  },
  logRendererDiagnostic(payload) {
    ipcRenderer.send("desktop:log-renderer-diagnostic", payload);
  },
});
