import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";

import { createAccountCenterClient } from "./api/account_center_client.js";
import { createProgramAuthClient } from "./api/program_auth_client.js";
import { getDesktopBootstrapConfig, subscribeDesktopBootstrapConfig } from "./desktop/bridge.js";
import {
  buildUnhandledRejectionDetails,
  buildWindowErrorDetails,
  logRendererDiagnostic,
} from "./desktop/renderer_diagnostics.js";
import { AccountCapabilityStatsPage } from "./features/account-capability-stats/account_capability_stats_page.jsx";
import { AccountCenterPage } from "./features/account-center/account_center_page.jsx";
import { DiagnosticsPanel } from "./features/diagnostics/diagnostics_panel.jsx";
import { useSidebarDiagnostics } from "./features/diagnostics/use_sidebar_diagnostics.js";
import { PurchaseSystemPage } from "./features/purchase-system/purchase_system_page.jsx";
import { QueryStatsPage } from "./features/query-stats/query_stats_page.jsx";
import { QuerySystemPage } from "./features/query-system/query_system_page.jsx";
import { AppShell } from "./features/shell/app_shell.jsx";
import { ProgramAccessSidebarCard } from "./program_access/program_access_sidebar_card.jsx";
import {
  ProgramAccessProvider,
  useProgramAccessGuard,
} from "./program_access/program_access_provider.jsx";
import {
  initializeRendererReloadNotice,
  readAppShellState,
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
  const [initialAppShellState] = useState(() => readAppShellState());
  const initialActiveItem = resolveKnownActiveItem(initialAppShellState.activeItem);
  const [bootstrapConfig, setBootstrapConfig] = useState(() => getDesktopBootstrapConfig());
  const [fallbackRuntimeStore] = useState(() => createAppRuntimeStore());
  const [activeItem, setActiveItem] = useState(initialActiveItem);
  const [mountedKeepAliveItems, setMountedKeepAliveItems] = useState(() => (
    createInitialMountedKeepAliveItems(initialAppShellState.activeItem)
  ));
  const [reloadNotice] = useState(() => initializeRendererReloadNotice({
    activeItem: initialActiveItem,
  }));
  const [navPrompt, setNavPrompt] = useState(EMPTY_NAV_PROMPT);
  const [querySystemLeaveState, setQuerySystemLeaveState] = useState(EMPTY_QUERY_SYSTEM_LEAVE_STATE);
  const [purchaseSystemLeaveState, setPurchaseSystemLeaveState] = useState(EMPTY_PURCHASE_SYSTEM_LEAVE_STATE);
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
    enabled: activeItem === "diagnostics",
  });
  const isBackendReady = bootstrapConfig.backendStatus === "ready";

  const handleQuerySystemLeaveStateChange = useCallback((nextState) => {
    setQuerySystemLeaveState(nextState || EMPTY_QUERY_SYSTEM_LEAVE_STATE);
  }, []);

  const handlePurchaseSystemLeaveStateChange = useCallback((nextState) => {
    setPurchaseSystemLeaveState(nextState || EMPTY_PURCHASE_SYSTEM_LEAVE_STATE);
  }, []);

  useEffect(() => {
    writeAppShellState({ activeItem });
    updateRendererActiveItem(activeItem);
  }, [activeItem]);

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

  useEffect(() => subscribeDesktopBootstrapConfig((nextBootstrapConfig) => {
    setBootstrapConfig((current) => {
      const nextApiBaseUrl = String(nextBootstrapConfig.apiBaseUrl || "");
      if (
        current.backendMode === nextBootstrapConfig.backendMode
        && current.backendStatus === nextBootstrapConfig.backendStatus
        && String(current.apiBaseUrl || "") === nextApiBaseUrl
        && String(current.runtimeWebSocketUrl || "") === String(nextBootstrapConfig.runtimeWebSocketUrl || "")
      ) {
        return current;
      }
      return nextBootstrapConfig;
    });
  }), []);

  useLayoutEffect(() => {
    if (!isBackendReady) {
      return;
    }

    void runtimeConnectionManager.bootstrap().catch(() => {});
  }, [
    isBackendReady,
    runtimeConnectionManager,
  ]);

  useEffect(() => {
    if (
      bootstrapConfig.backendMode !== "remote"
      || !isBackendReady
      || !bootstrapConfig.runtimeWebSocketUrl
      || !globalThis.WebSocket
    ) {
      return;
    }

    let cancelled = false;
    let disconnect = () => {};

    void runtimeConnectionManager.bootstrap()
      .then(() => {
        if (cancelled) {
          return;
        }
        disconnect = runtimeConnectionManager.connectRuntimeUpdates({
          websocketUrl: bootstrapConfig.runtimeWebSocketUrl,
          WebSocketImpl: globalThis.WebSocket,
        });
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      disconnect();
    };
  }, [
    bootstrapConfig.backendMode,
    isBackendReady,
    bootstrapConfig.runtimeWebSocketUrl,
    runtimeConnectionManager,
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
            {mountedKeepAliveItems["account-center"] ? (
              <div hidden={activeItem !== "account-center"}>
                <AccountCenterPage
                  bootstrapConfig={bootstrapConfig}
                  client={client}
                />
              </div>
            ) : null}
            {mountedKeepAliveItems["query-system"] ? (
              <div hidden={activeItem !== "query-system"}>
                <QuerySystemPage
                  bootstrapConfig={bootstrapConfig}
                  client={client}
                  isActive={activeItem === "query-system"}
                  onLeaveStateChange={handleQuerySystemLeaveStateChange}
                />
              </div>
            ) : null}
            {mountedKeepAliveItems["query-stats"] ? (
              <div hidden={activeItem !== "query-stats"}>
                <QueryStatsPage
                  bootstrapConfig={bootstrapConfig}
                  client={client}
                />
              </div>
            ) : null}
            {mountedKeepAliveItems["account-capability-stats"] ? (
              <div hidden={activeItem !== "account-capability-stats"}>
                <AccountCapabilityStatsPage
                  bootstrapConfig={bootstrapConfig}
                  client={client}
                />
              </div>
            ) : null}
            {mountedKeepAliveItems["purchase-system"] ? (
              <div hidden={activeItem !== "purchase-system"}>
                <PurchaseSystemPage
                  bootstrapConfig={bootstrapConfig}
                  client={client}
                  isActive={activeItem === "purchase-system"}
                  onLeaveStateChange={handlePurchaseSystemLeaveStateChange}
                />
              </div>
            ) : null}
            {mountedKeepAliveItems["diagnostics"] ? (
              <div hidden={activeItem !== "diagnostics"}>
                <DiagnosticsPanel
                  error={diagnostics.error}
                  isLoading={diagnostics.isLoading}
                  isRefreshing={diagnostics.isRefreshing}
                  snapshot={diagnostics.snapshot}
                />
              </div>
            ) : null}
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