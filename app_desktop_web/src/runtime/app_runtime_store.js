import {
  EMPTY_PROGRAM_ACCESS,
  normalizeProgramAccess,
  resolveProgramAccessPayload,
} from "../program_access/program_access_runtime.js";


function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}


function deepClone(value) {
  if (Array.isArray(value)) {
    return value.map((item) => deepClone(item));
  }

  if (!isPlainObject(value)) {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, nestedValue]) => [key, deepClone(nestedValue)]),
  );
}


function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }

  Object.freeze(value);
  Object.values(value).forEach((nestedValue) => {
    deepFreeze(nestedValue);
  });

  return value;
}


function finalizeValue(value) {
  return deepFreeze(value);
}


function hasOwnKey(value, key) {
  return Boolean(value) && Object.prototype.hasOwnProperty.call(value, key);
}

const QUERY_CONFIG_SERVER_SHAPE_SUMMARY = "summary";
const QUERY_CONFIG_SERVER_SHAPE_DETAIL = "detail";


const SNAPSHOT_TEMPLATE = createInitialSnapshot();


function createInitialSnapshot() {
  return finalizeValue({
    bootstrap: { state: "idle", hydratedAt: null, version: 0 },
    connection: { state: "idle", stale: false, lastSyncAt: null, lastEventVersion: 0, lastError: "" },
    programAccess: EMPTY_PROGRAM_ACCESS,
    querySystem: {
      serverHydrated: false,
      server: {
        configs: [],
        capacitySummary: { modes: {} },
        runtimeStatus: { running: false, item_rows: [] },
      },
      ui: { selectedConfigId: null },
      draft: { currentConfig: null, hasUnsavedChanges: false },
    },
    purchaseSystem: {
      serverHydrated: false,
      server: {
        runtimeStatus: { running: false, accounts: [], item_rows: [] },
        uiPreferences: {},
        runtimeSettings: {},
      },
      ui: { selectedConfigId: null, activeModal: "" },
      draft: { purchaseSettingsDraft: {}, querySettingsDraft: null },
    },
  });
}


function mergePatchValue(currentValue, nextValue) {
  if (nextValue === undefined) {
    return currentValue;
  }

  if (Array.isArray(nextValue)) {
    const nextArray = deepClone(nextValue);
    return finalizeValue(nextArray);
  }

  if (isPlainObject(currentValue) && isPlainObject(nextValue)) {
    let changed = false;
    const nextObject = {};
    const keys = new Set([...Object.keys(currentValue), ...Object.keys(nextValue)]);

    keys.forEach((key) => {
      const mergedValue = mergePatchValue(currentValue[key], nextValue[key]);
      nextObject[key] = mergedValue;
      changed = changed || !Object.is(mergedValue, currentValue[key]);
    });

    if (!changed && Object.keys(currentValue).length === Object.keys(nextObject).length) {
      return currentValue;
    }

    return finalizeValue(nextObject);
  }

  if (isPlainObject(nextValue)) {
    return finalizeValue(deepClone(nextValue));
  }

  return nextValue;
}


function mergeBootstrapValue(templateValue, currentValue, nextValue) {
  if (nextValue === undefined) {
    return currentValue;
  }

  if (Array.isArray(nextValue)) {
    return finalizeValue(deepClone(nextValue));
  }

  if (isPlainObject(templateValue)) {
    if (!isPlainObject(nextValue)) {
      return nextValue;
    }

    const nextObject = {};
    const templateKeys = Object.keys(templateValue);
    const nextKeys = Object.keys(nextValue);
    let changed = false;

    templateKeys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(nextValue, key)) {
        const mergedValue = mergeBootstrapValue(templateValue[key], currentValue?.[key], nextValue[key]);
        nextObject[key] = mergedValue;
        changed = changed || !Object.is(mergedValue, currentValue?.[key]);
        return;
      }

      nextObject[key] = currentValue?.[key] ?? templateValue[key];
    });

    nextKeys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(nextObject, key)) {
        return;
      }

      const mergedValue = mergeBootstrapValue(undefined, currentValue?.[key], nextValue[key]);
      nextObject[key] = mergedValue;
      changed = changed || !Object.is(mergedValue, currentValue?.[key]);
    });

    const currentKeys = isPlainObject(currentValue) ? Object.keys(currentValue) : [];

    if (
      !changed
      && currentKeys.length === Object.keys(nextObject).length
      && currentKeys.every((key) => Object.is(currentValue[key], nextObject[key]))
    ) {
      return currentValue;
    }

    return finalizeValue(nextObject);
  }

  if (isPlainObject(nextValue)) {
    return finalizeValue(deepClone(nextValue));
  }

  return nextValue;
}


function resolveBootstrapMetadata(payload, currentBootstrap) {
  const bootstrapPayload = isPlainObject(payload?.bootstrap) ? payload.bootstrap : payload;
  const version = bootstrapPayload?.version;
  const hydratedAt = bootstrapPayload?.generated_at ?? bootstrapPayload?.generatedAt ?? bootstrapPayload?.hydratedAt;
  const nextBootstrap = {
    state: "hydrated",
    version: version ?? currentBootstrap.version,
    hydratedAt: hydratedAt ?? currentBootstrap.hydratedAt,
  };

  if (
    currentBootstrap.state === nextBootstrap.state
    && currentBootstrap.version === nextBootstrap.version
    && currentBootstrap.hydratedAt === nextBootstrap.hydratedAt
  ) {
    return currentBootstrap;
  }

  return finalizeValue(nextBootstrap);
}


function resolveQueryServerPayload(payload) {
  const queryPayload = hasOwnKey(payload, "querySystem")
    ? payload.querySystem
    : hasOwnKey(payload, "query_system")
      ? payload.query_system
      : undefined;

  if (queryPayload === undefined) {
    return undefined;
  }

  return normalizeQueryServerPayload(queryPayload.server ?? queryPayload);
}


function resolvePurchaseServerPayload(payload) {
  const purchasePayload = hasOwnKey(payload, "purchaseSystem")
    ? payload.purchaseSystem
    : hasOwnKey(payload, "purchase_system")
      ? payload.purchase_system
      : undefined;

  if (purchasePayload === undefined) {
    return undefined;
  }

  return purchasePayload.server ?? purchasePayload;
}


function normalizeQueryConfigServerShape(serverShape) {
  return serverShape === QUERY_CONFIG_SERVER_SHAPE_DETAIL
    ? QUERY_CONFIG_SERVER_SHAPE_DETAIL
    : QUERY_CONFIG_SERVER_SHAPE_SUMMARY;
}


function normalizeQueryServerPayload(serverPayload) {
  if (!isPlainObject(serverPayload) || !Array.isArray(serverPayload.configs)) {
    return serverPayload;
  }

  return {
    ...serverPayload,
    configs: serverPayload.configs.map((config) => (
      isPlainObject(config)
        ? {
            ...config,
            serverShape: normalizeQueryConfigServerShape(config.serverShape),
          }
        : config
    )),
  };
}


export function createAppRuntimeStore() {
  const listeners = new Set();
  let snapshot = createInitialSnapshot();

  function emitChange() {
    listeners.forEach((listener) => listener());
  }

  function setSnapshot(nextSnapshot) {
    if (Object.is(nextSnapshot, snapshot)) {
      return snapshot;
    }

    snapshot = finalizeValue(nextSnapshot);
    emitChange();
    return snapshot;
  }

  function applyQueryServerSnapshot(serverPayload, { markHydrated = true } = {}) {
    const normalizedServerPayload = normalizeQueryServerPayload(serverPayload);
    const nextServer = mergeBootstrapValue(
      SNAPSHOT_TEMPLATE.querySystem.server,
      snapshot.querySystem.server,
      normalizedServerPayload,
    );
    const nextServerHydrated = markHydrated || snapshot.querySystem.serverHydrated;
    const nextQuerySystem = (
      nextServer === snapshot.querySystem.server
      && nextServerHydrated === snapshot.querySystem.serverHydrated
    )
      ? snapshot.querySystem
      : {
          ...snapshot.querySystem,
          serverHydrated: nextServerHydrated,
          server: nextServer,
        };

    if (nextQuerySystem === snapshot.querySystem) {
      return snapshot;
    }

    return setSnapshot({
      ...snapshot,
      querySystem: nextQuerySystem,
    });
  }

  function applyPurchaseServerSnapshot(serverPayload, { markHydrated = true } = {}) {
    const nextServer = mergeBootstrapValue(
      SNAPSHOT_TEMPLATE.purchaseSystem.server,
      snapshot.purchaseSystem.server,
      serverPayload,
    );
    const nextServerHydrated = markHydrated || snapshot.purchaseSystem.serverHydrated;
    const nextPurchaseSystem = (
      nextServer === snapshot.purchaseSystem.server
      && nextServerHydrated === snapshot.purchaseSystem.serverHydrated
    )
      ? snapshot.purchaseSystem
      : {
          ...snapshot.purchaseSystem,
          serverHydrated: nextServerHydrated,
          server: nextServer,
        };

    if (nextPurchaseSystem === snapshot.purchaseSystem) {
      return snapshot;
    }

    return setSnapshot({
      ...snapshot,
      purchaseSystem: nextPurchaseSystem,
    });
  }

  return {
    getSnapshot() {
      return snapshot;
    },
    subscribe(listener) {
      listeners.add(listener);

      return () => {
        listeners.delete(listener);
      };
    },
    applyBootstrap(payload = {}) {
      const hasQueryPayload = resolveQueryServerPayload(payload) !== undefined;
      const hasPurchasePayload = resolvePurchaseServerPayload(payload) !== undefined;
      const programAccessPayload = resolveProgramAccessPayload(payload);
      const nextQueryServer = hasQueryPayload
        ? mergeBootstrapValue(
            SNAPSHOT_TEMPLATE.querySystem.server,
            snapshot.querySystem.server,
            resolveQueryServerPayload(payload),
          )
        : snapshot.querySystem.server;
      const nextPurchaseServer = hasPurchasePayload
        ? mergeBootstrapValue(
            SNAPSHOT_TEMPLATE.purchaseSystem.server,
            snapshot.purchaseSystem.server,
            resolvePurchaseServerPayload(payload),
          )
        : snapshot.purchaseSystem.server;
      const nextProgramAccess = programAccessPayload !== undefined
        ? mergeBootstrapValue(
            SNAPSHOT_TEMPLATE.programAccess,
            snapshot.programAccess,
            normalizeProgramAccess(programAccessPayload),
          )
        : snapshot.programAccess;
      const nextBootstrap = resolveBootstrapMetadata(payload, snapshot.bootstrap);
      const nextQueryServerHydrated = hasQueryPayload ? true : snapshot.querySystem.serverHydrated;
      const nextPurchaseServerHydrated = hasPurchasePayload ? true : snapshot.purchaseSystem.serverHydrated;
      const nextQuerySystem = (
        nextQueryServer === snapshot.querySystem.server
        && nextQueryServerHydrated === snapshot.querySystem.serverHydrated
      )
        ? snapshot.querySystem
        : {
            ...snapshot.querySystem,
            serverHydrated: nextQueryServerHydrated,
            server: nextQueryServer,
          };
      const nextPurchaseSystem = (
        nextPurchaseServer === snapshot.purchaseSystem.server
        && nextPurchaseServerHydrated === snapshot.purchaseSystem.serverHydrated
      )
        ? snapshot.purchaseSystem
        : {
            ...snapshot.purchaseSystem,
            serverHydrated: nextPurchaseServerHydrated,
            server: nextPurchaseServer,
          };

      if (
        nextBootstrap === snapshot.bootstrap
        && nextProgramAccess === snapshot.programAccess
        && nextQuerySystem === snapshot.querySystem
        && nextPurchaseSystem === snapshot.purchaseSystem
      ) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        bootstrap: nextBootstrap,
        programAccess: nextProgramAccess,
        querySystem: nextQuerySystem,
        purchaseSystem: nextPurchaseSystem,
      });
    },
    patchBootstrap(patch = {}) {
      const nextBootstrap = mergePatchValue(snapshot.bootstrap, patch);

      if (nextBootstrap === snapshot.bootstrap) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        bootstrap: nextBootstrap,
      });
    },
    patchConnection(patch = {}) {
      const nextConnection = mergePatchValue(snapshot.connection, patch);

      if (nextConnection === snapshot.connection) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        connection: nextConnection,
      });
    },
    applyQuerySystemServer(serverPatch = {}) {
      return applyQueryServerSnapshot(serverPatch, { markHydrated: true });
    },
    patchQueryUi(patch = {}) {
      const nextUi = mergePatchValue(snapshot.querySystem.ui, patch);

      if (nextUi === snapshot.querySystem.ui) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        querySystem: {
          ...snapshot.querySystem,
          ui: nextUi,
        },
      });
    },
    patchQueryDraft(patch = {}) {
      const nextDraft = mergePatchValue(snapshot.querySystem.draft, patch);

      if (nextDraft === snapshot.querySystem.draft) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        querySystem: {
          ...snapshot.querySystem,
          draft: nextDraft,
        },
      });
    },
    applyPurchaseSystemServer(serverPatch = {}) {
      return applyPurchaseServerSnapshot(serverPatch, { markHydrated: true });
    },
    applyProgramAccess(programAccessPayload = {}) {
      const nextProgramAccess = mergeBootstrapValue(
        SNAPSHOT_TEMPLATE.programAccess,
        snapshot.programAccess,
        normalizeProgramAccess(programAccessPayload),
      );

      if (nextProgramAccess === snapshot.programAccess) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        programAccess: nextProgramAccess,
      });
    },
    patchPurchaseUi(patch = {}) {
      const nextUi = mergePatchValue(snapshot.purchaseSystem.ui, patch);

      if (nextUi === snapshot.purchaseSystem.ui) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        purchaseSystem: {
          ...snapshot.purchaseSystem,
          ui: nextUi,
        },
      });
    },
    patchPurchaseDraft(patch = {}) {
      const nextDraft = mergePatchValue(snapshot.purchaseSystem.draft, patch);

      if (nextDraft === snapshot.purchaseSystem.draft) {
        return snapshot;
      }

      return setSnapshot({
        ...snapshot,
        purchaseSystem: {
          ...snapshot.purchaseSystem,
          draft: nextDraft,
        },
      });
    },
  };
}
