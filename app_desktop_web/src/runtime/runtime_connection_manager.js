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


export function createRuntimeConnectionManager({
  client,
  store,
  now = () => new Date().toISOString(),
  schedule = (callback, delayMs = 0) => globalThis.setTimeout(callback, delayMs),
  resyncDelayMs = 0,
} = {}) {
  if (!client || typeof client.getAppBootstrap !== "function") {
    throw new Error("Runtime connection manager requires a client with getAppBootstrap().");
  }
  if (!store || typeof store.getSnapshot !== "function" || typeof store.applyBootstrap !== "function") {
    throw new Error("Runtime connection manager requires a compatible runtime store.");
  }

  let bootstrapPromise = null;
  let resyncScheduled = false;
  let runtimeStreamCleanup = null;

  function applyBootstrap(payload) {
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
      void bootstrap({ force: true }).catch(() => {});
    }, resyncDelayMs);
  }

  async function bootstrap({ force = false } = {}) {
    const snapshot = store.getSnapshot();

    if (!force && snapshot.bootstrap.state === "hydrated") {
      return snapshot;
    }

    if (bootstrapPromise) {
      return bootstrapPromise;
    }

    if (typeof store.patchBootstrap === "function") {
      store.patchBootstrap({ state: "loading" });
    }

    bootstrapPromise = (async () => {
      try {
        const payload = await client.getAppBootstrap();
        return applyBootstrap(payload);
      } catch (error) {
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
        bootstrapPromise = null;
      }
    })();

    return bootstrapPromise;
  }

  function connectRuntimeUpdates({
    websocketUrl,
    WebSocketImpl = globalThis.WebSocket,
    reconnectDelayMs = 1000,
  } = {}) {
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
      const websocket = new WebSocketImpl(nextUrl);
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

  return {
    applyBootstrap,
    bootstrap,
    connectRuntimeUpdates,
    markDisconnected,
    scheduleResync,
  };
}
