import { useCallback, useEffect, useState } from "react";

import { createAccountCenterClient } from "./api/account_center_client.js";
import { getDesktopBootstrapConfig } from "./desktop/bridge.js";
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
import {
  initializeRendererReloadNotice,
  readAppShellState,
  updateRendererActiveItem,
  writeAppShellState,
} from "./features/shell/app_shell_state.js";
import { UnsavedChangesDialog } from "./features/shell/unsaved_changes_dialog.jsx";


const EMPTY_QUERY_SYSTEM_LEAVE_STATE = {
  canPromptOnLeave: false,
  requestSave: async () => false,
};

const EMPTY_PURCHASE_SYSTEM_LEAVE_STATE = {
  canPromptOnLeave: false,
  requestSave: async () => false,
};

const EMPTY_NAV_PROMPT = {
  error: "",
  isOpen: false,
  isSaving: false,
  nextItem: null,
};


export function App() {
  const [initialAppShellState] = useState(() => readAppShellState());
  const [bootstrapConfig] = useState(() => getDesktopBootstrapConfig());
  const [activeItem, setActiveItem] = useState(initialAppShellState.activeItem);
  const [reloadNotice] = useState(() => initializeRendererReloadNotice({
    activeItem: initialAppShellState.activeItem,
  }));
  const [navPrompt, setNavPrompt] = useState(EMPTY_NAV_PROMPT);
  const [querySystemLeaveState, setQuerySystemLeaveState] = useState(EMPTY_QUERY_SYSTEM_LEAVE_STATE);
  const [purchaseSystemLeaveState, setPurchaseSystemLeaveState] = useState(EMPTY_PURCHASE_SYSTEM_LEAVE_STATE);
  const [client] = useState(() => createAccountCenterClient({
    apiBaseUrl: bootstrapConfig.apiBaseUrl,
    pollIntervalMs: 25,
  }));
  const diagnostics = useSidebarDiagnostics(client, {
    enabled: activeItem === "diagnostics",
  });

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

    setActiveItem(nextItem);
  }, [activeItem, activeLeaveState]);

  const handleDiscardAndLeave = useCallback(() => {
    if (!navPrompt.nextItem) {
      return;
    }

    setActiveItem(navPrompt.nextItem);
    setNavPrompt(EMPTY_NAV_PROMPT);
  }, [navPrompt.nextItem]);

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

    setActiveItem(nextItem);
    setNavPrompt(EMPTY_NAV_PROMPT);
  }, [activeLeaveState, navPrompt.nextItem]);

  return (
    <>
      <AppShell
        activeItem={activeItem}
        onSelect={handleSelectItem}
        reloadNotice={reloadNotice}
      >
        {activeItem === "query-system" ? (
          <QuerySystemPage
            bootstrapConfig={bootstrapConfig}
            client={client}
            onLeaveStateChange={handleQuerySystemLeaveStateChange}
          />
        ) : activeItem === "query-stats" ? (
          <QueryStatsPage
            bootstrapConfig={bootstrapConfig}
            client={client}
          />
        ) : activeItem === "account-capability-stats" ? (
          <AccountCapabilityStatsPage
            bootstrapConfig={bootstrapConfig}
            client={client}
          />
        ) : activeItem === "purchase-system" ? (
          <PurchaseSystemPage
            bootstrapConfig={bootstrapConfig}
            client={client}
            onLeaveStateChange={handlePurchaseSystemLeaveStateChange}
          />
        ) : activeItem === "diagnostics" ? (
          <DiagnosticsPanel
            error={diagnostics.error}
            isLoading={diagnostics.isLoading}
            isRefreshing={diagnostics.isRefreshing}
            snapshot={diagnostics.snapshot}
          />
        ) : (
          <AccountCenterPage
            bootstrapConfig={bootstrapConfig}
            client={client}
          />
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
  );
}
