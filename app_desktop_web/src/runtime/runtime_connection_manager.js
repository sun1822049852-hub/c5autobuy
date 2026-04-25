function hasOwnKey(value, key) {
  return Boolean(value) && Object.prototype.hasOwnProperty.call(value, key);
}


function normalizeReason(reason) {
  if (!reason) {
    return "unknown";
  }

  return reason instanceof Error ? reason.message : String(reason);
}


function resolveBootstrapContainer(payload) {
  if (hasOwnKey(payload, "bootstrap") && payload.bootstrap && typeof payload.bootstrap === "object") {
    return payload.bootstrap;
  }

  return payload;
}


function resolveBootstrapVersion(payload, fallbackVersion) {
  const bootstrap = resolveBootstrapContainer(payload);
  const version = bootstrap?.version;

  return version ?? fallbackVersion;
}


function normalizeVersion(value, fallbackVersion = 0) {
  const normalizedVersion = Number.parseInt(String(value ?? ""), 10);

  return Number.isFinite(normalizedVersion) && normalizedVersion >= 0
    ? normalizedVersion
    : fallbackVersion;
}


function buildRuntimeWebSocketUrl(websocketUrl, sinceVersion) {
  try {
    const url = new URL(websocketUrl);
    url.searchParams.set("since_version", String(Math.max(normalizeVersion(sinceVersion, 0), 0)));
    return url.toString();
  } catch {
    return websocketUrl;
  }
}


function applyRuntimeUpdate(store, payload) {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const event = String(payload.event || "");
  const eventPayload = payload.payload;

  switch (event) {
    case "query_runtime.updated":
      store.applyQuerySystemServer?.({ runtimeStatus: eventPayload });
      break;
    case "purchase_runtime.updated":
      store.applyPurchaseSystemServer?.({ runtimeStatus: eventPayload });
      break;
    case "query_configs.updated":
      store.applyQuerySystemServer?.({ configs: eventPayload?.configs });
      break;
    case "purchase_ui_preferences.updated":
      store.applyPurchaseSystemServer?.({ uiPreferences: eventPayload });
      break;
    case "runtime_settings.updated":
      store.applyPurchaseSystemServer?.({ runtimeSettings: eventPayload });
      break;
    case "program_access.updated":
      store.applyProgramAccess?.(eventPayload);
      break;
    default:
      break;
  }

  return event;
}


function hasDedicatedShellBootstrap(client) {
  return typeof client?.getAppBootstrapShell === "function";
}


function hasFullBootstrap(client) {
  return typeof client?.getAppBootstrapFull === "function"
    || typeof client?.getAppBootstrap === "function";
}


function fetchShellBootstrap(client) {
  if (hasDedicatedShellBootstrap(client)) {
    return client.getAppBootstrapShell();
  }

  if (typeof client?.getAppBootstrap === "function") {
    return client.getAppBootstrap();
  }

  if (typeof client?.getAppBootstrapFull === "function") {
    return client.getAppBootstrapFull();
  }

  throw new Error("Runtime connection manager requires a client with bootstrap fetch methods.");
}


function fetchFullBootstrap(client) {
  if (typeof client?.getAppBootstrapFull === "function") {
    return client.getAppBootstrapFull();
  }

  if (typeof client?.getAppBootstrap === "function") {
    return client.getAppBootstrap();
  }

  throw new Error("Runtime connection manager requires a client with full bootstrap fetch methods.");
}


export function createRuntimeConnectionManager({
  client,
  store,
  now = () => new Date().toISOString(),
  schedule = (callback, delayMs = 0) => globalThis.setTimeout(callback, delayMs),
  resyncDelayMs = 0,
} = {}) {
  if (!client || !hasFullBootstrap(client)) {
    throw new Error("Runtime connection manager requires a client with full bootstrap fetch methods.");
  }
  if (!store || typeof store.getSnapshot !== "function" || typeof store.applyBootstrap !== "function") {
    throw new Error("Runtime connection manager requires a compatible runtime store.");
  }

  let shellBootstrapPromise = null;
  let fullBootstrapPromise = null;
  let fullBootstrapHydrated = false;
  let resyncScheduled = false;
  let runtimeStreamCleanup = null;
  let disposed = false;

  function applyBootstrap(payload) {
    if (disposed) {
      return payload;
    }
    const snapshot = store.getSnapshot();
    const version = resolveBootstrapVersion(payload, snapshot.connection.lastEventVersion);

    store.applyBootstrap(payload);
    if (typeof store.patchConnection === "function") {
      store.patchConnection({
        state: "connected",
        stale: false,
        lastSyncAt: now(),
        lastEventVersion: version,
        lastError: "",
      });
    }

    return payload;
  }

  function markDisconnected(reason) {
    if (disposed) {
      return store.getSnapshot();
    }
    if (typeof store.patchConnection !== "function") {
      return store.getSnapshot();
    }

    return store.patchConnection({
      state: "disconnected",
      stale: true,
      lastError: normalizeReason(reason),
    });
  }

  function scheduleResync(reason) {
    if (disposed) {
      return null;
    }
    if (typeof store.patchConnection === "function") {
      store.patchConnection({
        state: "stale",
        stale: true,
        lastError: normalizeReason(reason),
      });
    }

    if (resyncScheduled) {
      return null;
    }

    resyncScheduled = true;
    return schedule(() => {
      resyncScheduled = false;
      void bootstrap({ force: true, requireFull: true }).catch(() => {});
    }, resyncDelayMs);
  }

  async function hydrateShellBootstrap({ force = false } = {}) {
    const snapshot = store.getSnapshot();

    if (!force && snapshot.bootstrap.state === "hydrated") {
      return snapshot;
    }

    if (shellBootstrapPromise) {
      return shellBootstrapPromise;
    }

    if (typeof store.patchBootstrap === "function") {
      store.patchBootstrap({ state: "loading" });
    }

    shellBootstrapPromise = (async () => {
      try {
        const payload = await fetchShellBootstrap(client);
        if (disposed) {
          return payload;
        }
        if (!hasDedicatedShellBootstrap(client)) {
          fullBootstrapHydrated = true;
        }
        return applyBootstrap(payload);
      } catch (error) {
        if (disposed) {
          throw error;
        }
        if (typeof store.patchBootstrap === "function" && snapshot.bootstrap.state !== "hydrated") {
          store.patchBootstrap({ state: "error" });
        }
        if (typeof store.patchConnection === "function") {
          store.patchConnection({
            state: "error",
            stale: true,
            lastError: normalizeReason(error),
          });
        }
        throw error;
      } finally {
        shellBootstrapPromise = null;
      }
    })();

    return shellBootstrapPromise;
  }

  function patchFullBootstrapFailure(error) {
    if (typeof store.patchConnection !== "function") {
      return;
    }

    store.patchConnection({
      state: "stale",
      stale: true,
      lastError: normalizeReason(error),
    });
  }

  async function hydrateFullBootstrap({ force = false } = {}) {
    if (!force && fullBootstrapHydrated) {
      return store.getSnapshot();
    }

    if (fullBootstrapPromise) {
      return fullBootstrapPromise;
    }

    fullBootstrapPromise = (async () => {
      try {
        const payload = await fetchFullBootstrap(client);
        if (disposed) {
          return payload;
        }
        fullBootstrapHydrated = true;
        return applyBootstrap(payload);
      } catch (error) {
        if (disposed) {
          throw error;
        }
        patchFullBootstrapFailure(error);
        throw error;
      } finally {
        fullBootstrapPromise = null;
      }
    })();

    return fullBootstrapPromise;
  }

  async function bootstrap({ force = false, requireFull = force } = {}) {
    const snapshot = store.getSnapshot();

    if (!force && snapshot.bootstrap.state === "hydrated") {
      if (!fullBootstrapHydrated) {
        if (requireFull) {
          return hydrateFullBootstrap({ force: false });
        }
        void hydrateFullBootstrap({ force: false }).catch(() => {});
      }
      return snapshot;
    }

    const shellPayload = await hydrateShellBootstrap({ force });
    if (requireFull) {
      if (!hasDedicatedShellBootstrap(client)) {
        return shellPayload;
      }
      return hydrateFullBootstrap({ force });
    }

    if (!fullBootstrapHydrated) {
      void hydrateFullBootstrap({ force: false }).catch(() => {});
    }
    return shellPayload;
  }

  async function bootstrapShellOnly({ force = false } = {}) {
    const snapshot = store.getSnapshot();

    if (!force && snapshot.bootstrap.state === "hydrated") {
      return snapshot;
    }

    return hydrateShellBootstrap({ force });
  }

  async function ensureFullBootstrap({ force = false } = {}) {
    if (!force && fullBootstrapHydrated) {
      return store.getSnapshot();
    }

    const shellPayload = await hydrateShellBootstrap({ force });
    if (!hasDedicatedShellBootstrap(client)) {
      return shellPayload;
    }

    return hydrateFullBootstrap({ force });
  }

  function connectRuntimeUpdates({
    websocketUrl,
    WebSocketImpl = globalThis.WebSocket,
    reconnectDelayMs = 1000,
  } = {}) {
    if (disposed) {
      return () => {};
    }
    runtimeStreamCleanup?.();
    runtimeStreamCleanup = null;

    if (!websocketUrl || !WebSocketImpl) {
      return () => {};
    }

    const state = {
      closed: false,
      reconnectTimer: null,
      websocket: null,
    };

    function clearReconnectTimer() {
      if (state.reconnectTimer === null) {
        return;
      }
      globalThis.clearTimeout?.(state.reconnectTimer);
      state.reconnectTimer = null;
    }

    function patchConnected(updatedAt, version) {
      if (typeof store.patchConnection !== "function") {
        return;
      }

      const snapshot = store.getSnapshot();
      store.patchConnection({
        state: "connected",
        stale: false,
        lastSyncAt: updatedAt ?? now(),
        lastEventVersion: normalizeVersion(version, snapshot.connection.lastEventVersion),
        lastError: "",
      });
    }

    function scheduleReconnect() {
      if (state.closed || state.reconnectTimer !== null) {
        return;
      }

      state.reconnectTimer = schedule(() => {
        state.reconnectTimer = null;
        openRuntimeStream();
      }, reconnectDelayMs);
    }

    function handleSocketClosed(reason) {
      if (state.closed) {
        return;
      }

      scheduleResync(reason);
      scheduleReconnect();
    }

    function openRuntimeStream() {
      if (state.closed) {
        return;
      }

      const snapshot = store.getSnapshot();
      const nextUrl = buildRuntimeWebSocketUrl(websocketUrl, snapshot.connection.lastEventVersion);
      let websocket = null;
      try {
        websocket = new WebSocketImpl(nextUrl);
      } catch (error) {
        state.websocket = null;
        handleSocketClosed(error);
        return;
      }
      state.websocket = websocket;

      websocket.onopen = () => {
        if (state.closed || state.websocket !== websocket) {
          return;
        }
        if (typeof store.patchConnection === "function") {
          store.patchConnection({
            state: "connected",
            stale: false,
            lastError: "",
          });
        }
      };

      websocket.onerror = () => {
        if (state.closed || state.websocket !== websocket) {
          return;
        }
        if (typeof store.patchConnection === "function") {
          store.patchConnection({
            state: "stale",
            stale: true,
            lastError: "WebSocket 运行时流连接失败",
          });
        }
      };

      websocket.onmessage = (event) => {
        if (state.closed || state.websocket !== websocket) {
          return;
        }

        let payload = null;
        try {
          payload = JSON.parse(typeof event.data === "string" ? event.data : String(event.data ?? ""));
        } catch {
          handleSocketClosed("runtime_websocket_invalid_payload");
          websocket.close?.();
          return;
        }

        const eventName = applyRuntimeUpdate(store, payload);
        patchConnected(payload?.updated_at, payload?.version);

        if (eventName === "runtime.resync_required") {
          handleSocketClosed("runtime_resync_required");
          websocket.close?.();
        }
      };

      websocket.onclose = () => {
        if (state.websocket === websocket) {
          state.websocket = null;
        }
        handleSocketClosed("runtime_websocket_closed");
      };
    }

    openRuntimeStream();

    runtimeStreamCleanup = () => {
      state.closed = true;
      clearReconnectTimer();
      const websocket = state.websocket;
      state.websocket = null;
      websocket?.close?.();
    };

    return () => {
      runtimeStreamCleanup?.();
      if (runtimeStreamCleanup) {
        runtimeStreamCleanup = null;
      }
    };
  }

  function dispose() {
    disposed = true;
    runtimeStreamCleanup?.();
    runtimeStreamCleanup = null;
    shellBootstrapPromise = null;
    fullBootstrapPromise = null;
  }

  return {
    applyBootstrap,
    bootstrap,
    bootstrapShellOnly,
    connectRuntimeUpdates,
    dispose,
    ensureFullBootstrap,
    markDisconnected,
    scheduleResync,
  };
}
