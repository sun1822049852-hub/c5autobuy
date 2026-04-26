import React, { Suspense, useEffect, useRef, useState } from "react";

import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";
import { logRendererDiagnostic } from "../../desktop/renderer_diagnostics.js";
import { AccountTable } from "./components/account_table.jsx";
import { OverviewCards } from "./components/overview_cards.jsx";
import { useAccountCenterPage } from "./hooks/use_account_center_page.js";

const AccountCenterLazySurfaces = React.lazy(() =>
  import("./account_center_lazy_surfaces.jsx").then((m) => ({ default: m.AccountCenterLazySurfaces }))
);

function readPerformanceNow() {
  return globalThis.performance?.now?.() ?? Date.now();
}


export function AccountCenterPage({ client }) {
  const firstRenderTraceRef = useRef(null);
  if (firstRenderTraceRef.current === null) {
    firstRenderTraceRef.current = {
      renderStartMs: readPerformanceNow(),
    };
  }
  const {
    activeFilter,
    accountLogs,
    apiKeyDialogAccount,
    browserProxyDialogAccount,
    closeApiKeyDialog,
    closeBrowserProxyDialog,
    closeContextMenu,
    closeCreateDialog,
    closeDeleteDialog,
    closeFeatureUnavailableDialog,
    closeLoginDrawer,
    confirmDeleteAccount,
    deleteDialogAccount,
    logsModalState,
    closeProxyDialog,
    closePurchaseDrawer,
    closeRemarkDialog,
    contextMenu,
    createDialogOpen,
    featureUnavailableDialog,
    deleteAccount,
    filteredRows,
    isDeletingAccount,
    isLoading,
    isReadonlyLocked,
    isOpeningBindingPage,
    loadError,
    loginDrawerAccount,
    openApiKeyDialog,
    openBrowserProxyDialog,
    openAccountOpenApiBindingPage,
    toggleApiQueryMode,
    toggleBrowserQueryMode,
    openContextMenu,
    openCreateDialog,
    openLogsModal,
    openNicknameDialog,
    openProxyDialog,
    openPurchaseStatus,
    overviewCards,
    proxyDialogAccount,
    purchaseDrawerState,
    refreshPurchaseConfigInventory,
    refreshAccounts,
    remarkDialogAccount,
    searchTerm,
    setActiveFilter,
    setSearchTerm,
    startupInitTrace,
    syncAccountOpenApi,
    startLoginFromDrawer,
    submitApiKey,
    submitBrowserProxy,
    submitCreate,
    submitProxy,
    submitPurchaseConfig,
    submitRemark,
    loginTaskSnapshot,
    isLoginTaskStarting,
  } = useAccountCenterPage({ client });
  if (firstRenderTraceRef.current.afterHookMs == null) {
    firstRenderTraceRef.current.afterHookMs = readPerformanceNow();
  }
  const [proxyPoolDialogOpen, setProxyPoolDialogOpen] = useState(false);
  const hasLoggedFirstCommitRef = useRef(false);
  const activeCardLabel = overviewCards.find((card) => card.id === activeFilter)?.label ?? "全部账号";
  const shouldRenderLazySurfaces = proxyPoolDialogOpen
    || createDialogOpen
    || featureUnavailableDialog.isOpen
    || Boolean(deleteDialogAccount)
    || Boolean(remarkDialogAccount)
    || Boolean(apiKeyDialogAccount)
    || Boolean(browserProxyDialogAccount)
    || Boolean(proxyDialogAccount)
    || purchaseDrawerState.open
    || Boolean(loginDrawerAccount)
    || logsModalState.isOpen
    || Boolean(contextMenu);
  const heroCards = [
    ...overviewCards,
    {
      id: "logs",
      isActive: logsModalState.isOpen,
      label: "日志",
      value: accountLogs.length,
      hint: "查看最近日志",
      onClick: openLogsModal,
    },
  ];
  if (firstRenderTraceRef.current.beforeReturnMs == null) {
    firstRenderTraceRef.current.beforeReturnMs = readPerformanceNow();
  }

  useEffect(() => {
    if (hasLoggedFirstCommitRef.current) {
      return;
    }
    hasLoggedFirstCommitRef.current = true;
    const firstRenderTrace = firstRenderTraceRef.current ?? {};
    logRendererDiagnostic("startup_trace_account_center_first_commit", {
      hasRows: filteredRows.length > 0,
      isLoading,
      hookInitMs: Number.isFinite(firstRenderTrace.afterHookMs - firstRenderTrace.renderStartMs)
        ? Math.max(0, Math.round((firstRenderTrace.afterHookMs - firstRenderTrace.renderStartMs) * 100) / 100)
        : null,
      renderTailMs: Number.isFinite(firstRenderTrace.beforeReturnMs - firstRenderTrace.afterHookMs)
        ? Math.max(0, Math.round((firstRenderTrace.beforeReturnMs - firstRenderTrace.afterHookMs) * 100) / 100)
        : null,
    });
    logRendererDiagnostic("startup_trace_account_center_render_breakdown", {
      accountCenterHookInit: startupInitTrace ?? null,
      hookInitMs: Number.isFinite(firstRenderTrace.afterHookMs - firstRenderTrace.renderStartMs)
        ? Math.max(0, Math.round((firstRenderTrace.afterHookMs - firstRenderTrace.renderStartMs) * 100) / 100)
        : null,
      renderTailMs: Number.isFinite(firstRenderTrace.beforeReturnMs - firstRenderTrace.afterHookMs)
        ? Math.max(0, Math.round((firstRenderTrace.beforeReturnMs - firstRenderTrace.afterHookMs) * 100) / 100)
        : null,
    });
  }, [filteredRows.length, isLoading, startupInitTrace]);

  return (
    <section className="account-page">
      <header className="account-page__hero">
        <div className="account-page__hero-main">
          <div className="account-page__hero-copy" style={NO_SELECT_STYLE}>
            <div className="account-page__eyebrow">C5 交易助手</div>
            <h1 className="account-page__title">
              {isLoading ? "账号中心加载中" : "账号中心"}
            </h1>
          </div>
        </div>

        <div className="account-page__hero-side">
          <div className="account-page__hero-overview">
            <OverviewCards
              activeFilter={activeFilter}
              cards={heroCards}
              className="overview-grid--compact-row"
              onSelect={setActiveFilter}
            />
          </div>
        </div>
      </header>

      <section className="account-page__toolbar account-page__toolbar--compact">
        <div className="account-page__toolbar-copy" style={NO_SELECT_STYLE}>
          <div className="account-page__toolbar-title">账号列表</div>
          <div className="account-page__toolbar-subtitle">
            当前聚焦 {activeCardLabel}
          </div>
        </div>
        <div className="account-page__toolbar-actions">
          <button
            className="ghost-button account-page__toolbar-button"
            type="button"
            onClick={() => setProxyPoolDialogOpen(true)}
          >
            代理管理
          </button>
          <button
            className="ghost-button account-page__toolbar-button account-page__toolbar-button--secondary"
            type="button"
            onClick={refreshAccounts}
          >
            刷新
          </button>
          <input
            aria-label="搜索账号"
            className="account-page__toolbar-search"
            type="search"
            placeholder="搜索昵称、代理、状态"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <button
            className="accent-button account-page__toolbar-button"
            type="button"
            disabled={isReadonlyLocked}
            onClick={openCreateDialog}
          >
            添加账号
          </button>
        </div>
      </section>

      <section className="account-page__table-panel">
        <AccountTable
          isLoading={isLoading}
          loadError={loadError}
          onApiKeyEdit={openApiKeyDialog}
          onApiQueryToggle={toggleApiQueryMode}
          onBrowserProxyClick={openBrowserProxyDialog}
          onBrowserQueryToggle={toggleBrowserQueryMode}
          mutationsDisabled={isReadonlyLocked}
          onNicknameClick={openNicknameDialog}
          onProxyClick={openProxyDialog}
          onPurchaseStatusClick={openPurchaseStatus}
          onRowContextMenu={openContextMenu}
          rows={filteredRows}
        />
      </section>
      {shouldRenderLazySurfaces ? (
        <Suspense fallback={null}>
          <AccountCenterLazySurfaces
            accountLogs={accountLogs}
            apiKeyDialogAccount={apiKeyDialogAccount}
            browserProxyDialogAccount={browserProxyDialogAccount}
            client={client}
            closeApiKeyDialog={closeApiKeyDialog}
            closeBrowserProxyDialog={closeBrowserProxyDialog}
            closeContextMenu={closeContextMenu}
            closeCreateDialog={closeCreateDialog}
            closeDeleteDialog={closeDeleteDialog}
            closeFeatureUnavailableDialog={closeFeatureUnavailableDialog}
            closeLoginDrawer={closeLoginDrawer}
            closeProxyDialog={closeProxyDialog}
            closePurchaseDrawer={closePurchaseDrawer}
            closeRemarkDialog={closeRemarkDialog}
            confirmDeleteAccount={confirmDeleteAccount}
            contextMenu={contextMenu}
            createDialogOpen={createDialogOpen}
            deleteAccount={deleteAccount}
            deleteDialogAccount={deleteDialogAccount}
            featureUnavailableDialog={featureUnavailableDialog}
            isDeletingAccount={isDeletingAccount}
            isLoginTaskStarting={isLoginTaskStarting}
            isOpeningBindingPage={isOpeningBindingPage}
            isReadonlyLocked={isReadonlyLocked}
            loginDrawerAccount={loginDrawerAccount}
            loginTaskSnapshot={loginTaskSnapshot}
            logsModalState={logsModalState}
            onCloseProxyPoolDialog={() => setProxyPoolDialogOpen(false)}
            openAccountOpenApiBindingPage={openAccountOpenApiBindingPage}
            proxyDialogAccount={proxyDialogAccount}
            proxyPoolDialogOpen={proxyPoolDialogOpen}
            purchaseDrawerState={purchaseDrawerState}
            refreshPurchaseConfigInventory={refreshPurchaseConfigInventory}
            remarkDialogAccount={remarkDialogAccount}
            startLoginFromDrawer={startLoginFromDrawer}
            submitApiKey={submitApiKey}
            submitBrowserProxy={submitBrowserProxy}
            submitCreate={submitCreate}
            submitProxy={submitProxy}
            submitPurchaseConfig={submitPurchaseConfig}
            submitRemark={submitRemark}
            syncAccountOpenApi={syncAccountOpenApi}
          />
        </Suspense>
      ) : null}
    </section>
  );
}
