import React, { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { createAccountCenterClient } from "./api/account_center_client.js";
import { createProgramAuthClient } from "./api/program_auth_client.js";
import { getDefaultDesktopBootstrapConfig, subscribeDesktopBootstrapConfig } from "./desktop/bridge.js";
import {
  buildUnhandledRejectionDetails,
  buildWindowErrorDetails,
  logRendererDiagnostic,
} from "./desktop/renderer_diagnostics.js";
import { useSidebarDiagnostics } from "./features/diagnostics/use_sidebar_diagnostics.js";

// Lazy-loaded non-first-screen pages (code-split for faster initial load)
function loadAccountCenterPage() {
  logRendererDiagnostic("startup_trace_account_center_lazy_requested", {
    module: "account-center",
  });
  return import("./features/account-center/account_center_page.jsx").then((m) => {
    logRendererDiagnostic("startup_trace_account_center_chunk_ready", {
      module: "account-center",
    });
    return { default: m.AccountCenterPage };
  });
}

const AccountCenterPage = React.lazy(loadAccountCenterPage);
const QuerySystemPage = React.lazy(() =>
  import("./features/query-system/query_system_page.jsx").then(m => ({ default: m.QuerySystemPage }))
);
const PurchaseSystemPage = React.lazy(() =>
  import("./features/purchase-system/purchase_system_page.jsx").then(m => ({ default: m.PurchaseSystemPage }))
);
const QueryStatsPage = React.lazy(() =>
  import("./features/query-stats/query_stats_page.jsx").then(m => ({ default: m.QueryStatsPage }))
);
const AccountCapabilityStatsPage = React.lazy(() =>
  import("./features/account-capability-stats/account_capability_stats_page.jsx").then(m => ({ default: m.AccountCapabilityStatsPage }))
);
const DiagnosticsPanel = React.lazy(() =>
  import("./features/diagnostics/diagnostics_panel.jsx").then(m => ({ default: m.DiagnosticsPanel }))
);
import { AppShell } from "./features/shell/app_shell.jsx";
import { ProgramAccessSidebarCard } from "./program_access/program_access_sidebar_card.jsx";
import {
  ProgramAccessProvider,
  useProgramAccessGuard,
} from "./program_access/program_access_provider.jsx";
import {
  updateRendererActiveItem,
  writeAppShellState,
} from "./features/shell/app_shell_state.js";
import { UnsavedChangesDialog } from "./features/shell/unsaved_changes_dialog.jsx";
import { AppRuntimeProvider } from "./runtime/app_runtime_provider.jsx";
import { createAppRuntimeStore } from "./runtime/app_runtime_store.js";
import { createRuntimeConnectionManager } from "./runtime/runtime_connection_manager.js";
import { useProgramAccess } from "./runtime/use_app_runtime.js";


const EMPTY_QUERY_SYSTEM_LEAVE_STATE = {
  canPromptOnLeave: false,
  requestDiscard: async () => true,
  requestSave: async () => false,
};

const EMPTY_PURCHASE_SYSTEM_LEAVE_STATE = {
  canPromptOnLeave: false,
  requestDiscard: async () => true,
  requestSave: async () => false,
};

const EMPTY_NAV_PROMPT = {
  error: "",
  isOpen: false,
  isSaving: false,
  nextItem: null,
};

const KEEPALIVE_PAGE_IDS = [
  "account-center",
  "query-system",
  "purchase-system",
  "query-stats",
  "account-capability-stats",
  "diagnostics",
];

const FULL_BOOTSTRAP_PAGE_IDS = [
  "query-system",
  "purchase-system",
  "query-stats",
  "account-capability-stats",
  "diagnostics",
];


function resolveKnownActiveItem(activeItem) {
  return KEEPALIVE_PAGE_IDS.includes(activeItem) ? activeItem : "account-center";
}


function createInitialMountedKeepAliveItems(activeItem) {
  const resolvedActiveItem = resolveKnownActiveItem(activeItem);
  return Object.fromEntries(
    KEEPALIVE_PAGE_IDS.map((itemId) => [
      itemId,
      itemId === "account-center" || itemId === resolvedActiveItem,
    ]),
  );
}


function ProgramAccessShellBanner() {
  const programAccess = useProgramAccess();
  const {
    lastGuardError,
    lastProgramAuthError,
    refreshProgramAuthStatus,
    loginProgramAuth,
    logoutProgramAuth,
    sendRegisterCode,
    registerProgramAuth,
    verifyRegisterCode,
    completeRegisterProgramAuth,
    sendResetPasswordCode,
    resetProgramAuthPassword,
  } = useProgramAccessGuard();

  return (
    <ProgramAccessSidebarCard
      access={programAccess}
      guardError={lastGuardError}
      lastProgramAuthError={lastProgramAuthError}
      refreshProgramAuthStatus={refreshProgramAuthStatus}
      loginProgramAuth={loginProgramAuth}
      logoutProgramAuth={logoutProgramAuth}
      sendRegisterCode={sendRegisterCode}
      registerProgramAuth={registerProgramAuth}
      verifyRegisterCode={verifyRegisterCode}
      completeRegisterProgramAuth={completeRegisterProgramAuth}
      sendResetPasswordCode={sendResetPasswordCode}
      resetProgramAuthPassword={resetProgramAuthPassword}
    />
  );
}

function BackendStartupPanel({ backendStatus }) {
  const title = backendStatus === "failed" ? "本地服务启动失败" : "本地服务启动中";
  const message = backendStatus === "failed"
    ? "主界面已打开，但本地服务未成功接管。请关闭程序后重试。"
    : "主界面已进入，正在启动本地服务并接管首页数据。";

  return (
    <section className="app-shell__startup-panel" role="status">
      <span className="app-shell__startup-panel-eyebrow">Desktop Bootstrap</span>
      <h1 className="app-shell__startup-panel-title">{title}</h1>
      <p className="app-shell__startup-panel-text">{message}</p>
    </section>
  );
}


export function App({ runtimeStore }) {
  const initialActiveItem = "account-center";
  const [bootstrapConfig, setBootstrapConfig] = useState(() => getDefaultDesktopBootstrapConfig());
  const [fallbackRuntimeStore] = useState(() => createAppRuntimeStore());
  const [activeItem, setActiveItem] = useState(initialActiveItem);
  const [mountedKeepAliveItems, setMountedKeepAliveItems] = useState(() => (
    createInitialMountedKeepAliveItems(initialActiveItem)
  ));
  const [reloadNotice] = useState(() => null);
  const [shellStatePersistenceEnabled, setShellStatePersistenceEnabled] = useState(false);
  const hasReportedBootstrapConfigConsumedRef = useRef(false);
  const hasReportedAccountCenterRenderRequestedRef = useRef(false);
  const hasReportedHomeInteractiveRef = useRef(false);
  const [navPrompt, setNavPrompt] = useState(EMPTY_NAV_PROMPT);
  const [querySystemLeaveState, setQuerySystemLeaveState] = useState(EMPTY_QUERY_SYSTEM_LEAVE_STATE);
  const [purchaseSystemLeaveState, setPurchaseSystemLeaveState] = useState(EMPTY_PURCHASE_SYSTEM_LEAVE_STATE);
  const [fullBootstrapState, setFullBootstrapState] = useState({
    error: "",
    status: "idle",
  });
  const fullBootstrapPromiseRef = useRef(null);
  const fullBootstrapGenerationRef = useRef(0);
  const appRuntimeStore = runtimeStore ?? fallbackRuntimeStore;
  const client = useMemo(() => createAccountCenterClient({
    apiBaseUrl: bootstrapConfig.apiBaseUrl,
    pollIntervalMs: 25,
  }), [bootstrapConfig.apiBaseUrl]);
  const programAuthClient = useMemo(() => createProgramAuthClient({
    apiBaseUrl: bootstrapConfig.apiBaseUrl,
  }), [bootstrapConfig.apiBaseUrl]);
  const runtimeConnectionManager = useMemo(() => createRuntimeConnectionManager({
    client,
    store: appRuntimeStore,
  }), [appRuntimeStore, client]);
  const diagnostics = useSidebarDiagnostics(client, {
    enabled: activeItem === "diagnostics" && fullBootstrapState.status === "ready",
  });
  const isBackendReady = bootstrapConfig.backendStatus === "ready";

  const requestFullBootstrap = useCallback(({ force = false } = {}) => {
    if (fullBootstrapPromiseRef.current) {
      return fullBootstrapPromiseRef.current;
    }
    const generation = fullBootstrapGenerationRef.current;

    setFullBootstrapState((current) => (
      current.status === "ready"
        && !force
        ? current
        : {
            error: "",
            status: "loading",
          }
    ));

    const nextPromise = Promise.resolve()
      .then(() => runtimeConnectionManager.ensureFullBootstrap({ force }))
      .then((result) => {
        if (fullBootstrapGenerationRef.current === generation) {
          setFullBootstrapState({
            error: "",
            status: "ready",
          });
        }
        return result;
      })
      .catch((error) => {
        if (fullBootstrapGenerationRef.current === generation) {
          setFullBootstrapState({
            error: error instanceof Error ? error.message : String(error ?? "unknown"),
            status: "error",
          });
        }
        throw error;
      })
      .finally(() => {
        if (
          fullBootstrapGenerationRef.current === generation
          && fullBootstrapPromiseRef.current === nextPromise
        ) {
          fullBootstrapPromiseRef.current = null;
        }
      });

    fullBootstrapPromiseRef.current = nextPromise;
    return nextPromise;
  }, [runtimeConnectionManager]);

  const handleRetryFullBootstrap = useCallback(() => {
    void requestFullBootstrap({ force: true }).catch(() => {});
  }, [requestFullBootstrap]);

  const handleQuerySystemLeaveStateChange = useCallback((nextState) => {
    setQuerySystemLeaveState(nextState || EMPTY_QUERY_SYSTEM_LEAVE_STATE);
  }, []);

  const handlePurchaseSystemLeaveStateChange = useCallback((nextState) => {
    setPurchaseSystemLeaveState(nextState || EMPTY_PURCHASE_SYSTEM_LEAVE_STATE);
  }, []);

  useEffect(() => {
    if (!shellStatePersistenceEnabled) {
      return;
    }
    writeAppShellState({ activeItem });
    updateRendererActiveItem(activeItem);
  }, [activeItem, shellStatePersistenceEnabled]);

  useEffect(() => {
    logRendererDiagnostic("renderer_navigation_state", {
      activeItem,
    });
  }, [activeItem]);

  useEffect(() => {
    if (!reloadNotice) {
      return;
    }
    logRendererDiagnostic("renderer_reload_detected", reloadNotice);
  }, [reloadNotice]);

  useLayoutEffect(() => {
    return subscribeDesktopBootstrapConfig((nextBootstrapConfig) => {
      const normalizedApiBaseUrl = String(nextBootstrapConfig.apiBaseUrl || "");
      if (
        nextBootstrapConfig.backendStatus === "ready"
        && !hasReportedBootstrapConfigConsumedRef.current
      ) {
        hasReportedBootstrapConfigConsumedRef.current = true;
        logRendererDiagnostic("startup_trace_bootstrap_config_consumed", {
          apiBaseUrl: normalizedApiBaseUrl,
          backendMode: nextBootstrapConfig.backendMode,
          backendStatus: nextBootstrapConfig.backendStatus,
        });
      }

      setBootstrapConfig((current) => {
        if (
          current.backendMode === nextBootstrapConfig.backendMode
          && current.backendStatus === nextBootstrapConfig.backendStatus
          && String(current.apiBaseUrl || "") === normalizedApiBaseUrl
          && String(current.runtimeWebSocketUrl || "") === String(nextBootstrapConfig.runtimeWebSocketUrl || "")
        ) {
          return current;
        }
        return nextBootstrapConfig;
      });
    });
  }, []);

  useEffect(() => {
    return () => {
      runtimeConnectionManager.dispose?.();
    };
  }, [runtimeConnectionManager]);

  useEffect(() => {
    fullBootstrapGenerationRef.current += 1;
    fullBootstrapPromiseRef.current = null;
    setFullBootstrapState({
      error: "",
      status: "idle",
    });
  }, [runtimeConnectionManager]);

  useLayoutEffect(() => {
    if (!isBackendReady) {
      return;
    }

    void runtimeConnectionManager.bootstrapShellOnly().catch(() => {});
  }, [
    isBackendReady,
    runtimeConnectionManager,
  ]);

  useLayoutEffect(() => {
    if (
      !isBackendReady
      || activeItem !== "account-center"
      || hasReportedAccountCenterRenderRequestedRef.current
    ) {
      return;
    }

    hasReportedAccountCenterRenderRequestedRef.current = true;
    logRendererDiagnostic("startup_trace_account_center_render_requested", {
      activeItem,
    });
  }, [activeItem, isBackendReady]);

  useEffect(() => {
    if (
      bootstrapConfig.backendMode !== "remote"
      || !isBackendReady
      || !FULL_BOOTSTRAP_PAGE_IDS.includes(activeItem)
      || !bootstrapConfig.runtimeWebSocketUrl
      || !globalThis.WebSocket
      || fullBootstrapState.status !== "ready"
    ) {
      return;
    }

    let disconnect = () => {};

    disconnect = runtimeConnectionManager.connectRuntimeUpdates({
      websocketUrl: bootstrapConfig.runtimeWebSocketUrl,
      WebSocketImpl: globalThis.WebSocket,
    });

    return () => {
      disconnect();
    };
  }, [
    activeItem,
    bootstrapConfig.backendMode,
    fullBootstrapState.status,
    isBackendReady,
    bootstrapConfig.runtimeWebSocketUrl,
    runtimeConnectionManager,
  ]);

  useEffect(() => {
    if (!isBackendReady || !FULL_BOOTSTRAP_PAGE_IDS.includes(activeItem)) {
      return;
    }

    void requestFullBootstrap().catch(() => {});
  }, [
    activeItem,
    isBackendReady,
    requestFullBootstrap,
  ]);

  useEffect(() => {
    function handleWindowError(event) {
      logRendererDiagnostic("renderer_window_error", buildWindowErrorDetails(event));
      event.preventDefault?.();
    }

    function handleUnhandledRejection(event) {
      logRendererDiagnostic("renderer_unhandled_rejection", buildUnhandledRejectionDetails(event));
      event.preventDefault?.();
    }

    globalThis.window?.addEventListener("error", handleWindowError);
    globalThis.window?.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      globalThis.window?.removeEventListener("error", handleWindowError);
      globalThis.window?.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  useEffect(() => {
    if (
      !isBackendReady
      || activeItem !== "account-center"
      || hasReportedHomeInteractiveRef.current
    ) {
      return undefined;
    }

    let timeoutId = null;
    let rafId = null;
    const doc = globalThis.document;
    const scheduleNextCheck = typeof globalThis.requestAnimationFrame === "function"
      ? (callback) => {
          rafId = globalThis.requestAnimationFrame(callback);
        }
      : (callback) => {
          timeoutId = globalThis.setTimeout(callback, 16);
        };

    const emitWhenHomeToolbarReady = () => {
      if (doc?.querySelector(".account-page__toolbar")) {
        hasReportedHomeInteractiveRef.current = true;
        setShellStatePersistenceEnabled(true);
        logRendererDiagnostic("startup_trace_home_interactive", {
          selector: ".account-page__toolbar",
        });
        return;
      }
      scheduleNextCheck(emitWhenHomeToolbarReady);
    };

    emitWhenHomeToolbarReady();

    return () => {
      if (rafId !== null && typeof globalThis.cancelAnimationFrame === "function") {
        globalThis.cancelAnimationFrame(rafId);
      }
      if (timeoutId !== null && typeof globalThis.clearTimeout === "function") {
        globalThis.clearTimeout(timeoutId);
      }
    };
  }, [activeItem, isBackendReady]);

  const activeLeaveState = activeItem === "query-system"
    ? querySystemLeaveState
    : activeItem === "purchase-system"
      ? purchaseSystemLeaveState
      : EMPTY_QUERY_SYSTEM_LEAVE_STATE;

  const activateItem = useCallback((nextItem) => {
    if (KEEPALIVE_PAGE_IDS.includes(nextItem)) {
      setMountedKeepAliveItems((current) => (
        current[nextItem]
          ? current
          : {
            ...current,
            [nextItem]: true,
          }
      ));
    }
    setActiveItem(resolveKnownActiveItem(nextItem));
  }, []);

  const handleSelectItem = useCallback((nextItem) => {
    if (!nextItem || nextItem === activeItem) {
      return;
    }

    if (nextItem !== activeItem && activeLeaveState.canPromptOnLeave) {
      setNavPrompt({
        error: "",
        isOpen: true,
        isSaving: false,
        nextItem,
      });
      return;
    }

    activateItem(nextItem);
  }, [activeItem, activeLeaveState, activateItem]);

  const handleDiscardAndLeave = useCallback(async () => {
    if (!navPrompt.nextItem) {
      return;
    }

    const discarded = await activeLeaveState.requestDiscard();
    if (!discarded) {
      return;
    }

    activateItem(navPrompt.nextItem);
    setNavPrompt(EMPTY_NAV_PROMPT);
  }, [activateItem, activeLeaveState, navPrompt.nextItem]);

  const handleSaveAndLeave = useCallback(async () => {
    if (!navPrompt.nextItem) {
      return;
    }

    setNavPrompt((current) => ({
      ...current,
      error: "",
      isSaving: true,
    }));

    const nextItem = navPrompt.nextItem;
    const saved = await activeLeaveState.requestSave();
    if (!saved) {
      setNavPrompt((current) => ({
        ...current,
        error: "保存失败，请先修复后再离开。",
        isSaving: false,
      }));
      return;
    }

    activateItem(nextItem);
    setNavPrompt(EMPTY_NAV_PROMPT);
  }, [activateItem, activeLeaveState, navPrompt.nextItem]);

  return (
    <AppRuntimeProvider store={appRuntimeStore}>
      <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={appRuntimeStore}>
        <>
          <AppShell
            activeItem={activeItem}
            onSelect={handleSelectItem}
            reloadNotice={reloadNotice}
            sidebarTopContent={<ProgramAccessShellBanner />}
          >
            {!isBackendReady ? (
              <BackendStartupPanel backendStatus={bootstrapConfig.backendStatus} />
            ) : (
              <>
                {mountedKeepAliveItems["account-center"] ? (
                  <div hidden={activeItem !== "account-center"}>
                    <Suspense fallback={null}>
                      <AccountCenterPage
                        bootstrapConfig={bootstrapConfig}
                        client={client}
                      />
                    </Suspense>
                  </div>
                ) : null}
                {mountedKeepAliveItems["query-system"] ? (
                  <div hidden={activeItem !== "query-system"}>
                    <Suspense fallback={null}>
                      <QuerySystemPage
                        bootstrapConfig={bootstrapConfig}
                        client={client}
                        isActive={activeItem === "query-system"}
                        onLeaveStateChange={handleQuerySystemLeaveStateChange}
                        onRetryBootstrap={handleRetryFullBootstrap}
                        runtimeBootstrapError={fullBootstrapState.error}
                        runtimeBootstrapStatus={fullBootstrapState.status}
                      />
                    </Suspense>
                  </div>
                ) : null}
                {mountedKeepAliveItems["query-stats"] ? (
                  <div hidden={activeItem !== "query-stats"}>
                    <Suspense fallback={null}>
                      <QueryStatsPage
                        bootstrapConfig={bootstrapConfig}
                        client={client}
                        onRetryBootstrap={handleRetryFullBootstrap}
                        runtimeBootstrapError={fullBootstrapState.error}
                        runtimeBootstrapStatus={fullBootstrapState.status}
                      />
                    </Suspense>
                  </div>
                ) : null}
                {mountedKeepAliveItems["account-capability-stats"] ? (
                  <div hidden={activeItem !== "account-capability-stats"}>
                    <Suspense fallback={null}>
                      <AccountCapabilityStatsPage
                        bootstrapConfig={bootstrapConfig}
                        client={client}
                        onRetryBootstrap={handleRetryFullBootstrap}
                        runtimeBootstrapError={fullBootstrapState.error}
                        runtimeBootstrapStatus={fullBootstrapState.status}
                      />
                    </Suspense>
                  </div>
                ) : null}
                {mountedKeepAliveItems["purchase-system"] ? (
                  <div hidden={activeItem !== "purchase-system"}>
                    <Suspense fallback={null}>
                      <PurchaseSystemPage
                        bootstrapConfig={bootstrapConfig}
                        client={client}
                        isActive={activeItem === "purchase-system"}
                        onLeaveStateChange={handlePurchaseSystemLeaveStateChange}
                        onRetryBootstrap={handleRetryFullBootstrap}
                        runtimeBootstrapError={fullBootstrapState.error}
                        runtimeBootstrapStatus={fullBootstrapState.status}
                      />
                    </Suspense>
                  </div>
                ) : null}
                {mountedKeepAliveItems["diagnostics"] ? (
                  <div hidden={activeItem !== "diagnostics"}>
                    <Suspense fallback={null}>
                      <DiagnosticsPanel
                        error={diagnostics.error}
                        isLoading={diagnostics.isLoading}
                        isRefreshing={diagnostics.isRefreshing}
                        onRetryBootstrap={handleRetryFullBootstrap}
                        runtimeBootstrapError={fullBootstrapState.error}
                        runtimeBootstrapStatus={fullBootstrapState.status}
                        snapshot={diagnostics.snapshot}
                      />
                    </Suspense>
                  </div>
                ) : null}
              </>
            )}
          </AppShell>

          <UnsavedChangesDialog
            error={navPrompt.error}
            isOpen={navPrompt.isOpen}
            isSaving={navPrompt.isSaving}
            onDiscard={handleDiscardAndLeave}
            onSave={handleSaveAndLeave}
          />
        </>
      </ProgramAccessProvider>
    </AppRuntimeProvider>
  );
}
