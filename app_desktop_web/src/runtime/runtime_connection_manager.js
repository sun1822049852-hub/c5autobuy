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

  return {
    applyBootstrap,
    bootstrap,
    markDisconnected,
    scheduleResync,
  };
}
