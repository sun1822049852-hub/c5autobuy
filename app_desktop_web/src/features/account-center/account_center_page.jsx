import { useEffect, useRef, useState } from "react";

import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";
import { logRendererDiagnostic } from "../../desktop/renderer_diagnostics.js";
import { ProxyPoolDialog } from "../proxy-pool/proxy_pool_dialog.jsx";
import { useProxyPool } from "../proxy-pool/use_proxy_pool.js";
import { AccountContextMenu } from "./components/account_context_menu.jsx";
import { AccountLogsModal } from "./components/account_logs_modal.jsx";
import { AccountTable } from "./components/account_table.jsx";
import { OverviewCards } from "./components/overview_cards.jsx";
import { AccountApiKeyDialog } from "./dialogs/account_api_key_dialog.jsx";
import { AccountBrowserProxyDialog } from "./dialogs/account_browser_proxy_dialog.jsx";
import { AccountCreateDialog } from "./dialogs/account_create_dialog.jsx";
import { AccountDeleteDialog } from "./dialogs/account_delete_dialog.jsx";
import { FeatureUnavailableDialog } from "./dialogs/feature_unavailable_dialog.jsx";
import { AccountProxyDialog } from "./dialogs/account_proxy_dialog.jsx";
import { AccountRemarkDialog } from "./dialogs/account_remark_dialog.jsx";
import { LoginDrawer } from "./drawers/login_drawer.jsx";
import { PurchaseConfigDrawer } from "./drawers/purchase_config_drawer.jsx";
import { useAccountCenterPage } from "./hooks/use_account_center_page.js";


export function AccountCenterPage({ client }) {
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
  const [proxyPoolDialogOpen, setProxyPoolDialogOpen] = useState(false);
  const shouldLoadProxyPool = proxyPoolDialogOpen
    || createDialogOpen
    || Boolean(browserProxyDialogAccount)
    || Boolean(proxyDialogAccount);
  const proxyPool = useProxyPool({ client, enabled: shouldLoadProxyPool });
  const hasLoggedFirstCommitRef = useRef(false);
  const activeCardLabel = overviewCards.find((card) => card.id === activeFilter)?.label ?? "全部账号";
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

  useEffect(() => {
    if (hasLoggedFirstCommitRef.current) {
      return;
    }
    hasLoggedFirstCommitRef.current = true;
    logRendererDiagnostic("startup_trace_account_center_first_commit", {
      hasRows: filteredRows.length > 0,
      isLoading,
    });
  }, [filteredRows.length, isLoading]);

  return (
    <section className="account-page">
      <header className="account-page__hero">
        <div className="account-page__hero-main">
          <div className="account-page__hero-copy" style={NO_SELECT_STYLE}>
            <div className="account-page__eyebrow">账号中心</div>
            <h1 className="account-page__title">
              {isLoading ? "账号中心加载中" : "C5 交易助手"}
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

      <AccountCreateDialog open={createDialogOpen} onClose={closeCreateDialog} onSubmit={submitCreate} proxies={proxyPool.proxies} />
      <FeatureUnavailableDialog
        isOpen={featureUnavailableDialog.isOpen}
        message={featureUnavailableDialog.message}
        onClose={closeFeatureUnavailableDialog}
      />
      <AccountDeleteDialog
        account={deleteDialogAccount}
        isDeleting={isDeletingAccount}
        open={Boolean(deleteDialogAccount)}
        onClose={closeDeleteDialog}
        onConfirm={confirmDeleteAccount}
      />
      <AccountRemarkDialog account={remarkDialogAccount} open={Boolean(remarkDialogAccount)} onClose={closeRemarkDialog} onSubmit={submitRemark} />
      <AccountApiKeyDialog account={apiKeyDialogAccount} open={Boolean(apiKeyDialogAccount)} onClose={closeApiKeyDialog} onSubmit={submitApiKey} />
      <AccountBrowserProxyDialog
        account={browserProxyDialogAccount}
        open={Boolean(browserProxyDialogAccount)}
        onClose={closeBrowserProxyDialog}
        onSubmit={submitBrowserProxy}
        proxies={proxyPool.proxies}
      />
      <AccountProxyDialog
        account={proxyDialogAccount}
        isOpeningBindingPage={isOpeningBindingPage}
        open={Boolean(proxyDialogAccount)}
        onClose={closeProxyDialog}
        onOpenBindingPage={openAccountOpenApiBindingPage}
        onSubmit={submitProxy}
        proxies={proxyPool.proxies}
      />
      <PurchaseConfigDrawer
        account={purchaseDrawerState.account}
        detail={purchaseDrawerState.detail}
        isLoading={purchaseDrawerState.isLoading}
        isRefreshing={purchaseDrawerState.isRefreshing}
        open={purchaseDrawerState.open}
        onClose={closePurchaseDrawer}
        onRefresh={refreshPurchaseConfigInventory}
        onSubmit={submitPurchaseConfig}
      />
      <LoginDrawer
        account={loginDrawerAccount}
        isStarting={isLoginTaskStarting}
        onClose={closeLoginDrawer}
        onStartLogin={startLoginFromDrawer}
        open={Boolean(loginDrawerAccount)}
        task={loginTaskSnapshot}
      />
      <AccountLogsModal
        entries={accountLogs}
        isOpen={logsModalState.isOpen}
        onClose={logsModalState.onClose}
        onPositionChange={logsModalState.onPositionChange}
        onSizeChange={logsModalState.onSizeChange}
        position={logsModalState.position}
        size={logsModalState.size}
      />
      <AccountContextMenu
        menu={contextMenu}
        mutationsDisabled={isReadonlyLocked}
        onClose={closeContextMenu}
        onDelete={deleteAccount}
        onOpenOpenApiBindingPage={openAccountOpenApiBindingPage}
        onSyncOpenApi={syncAccountOpenApi}
      />
      <ProxyPoolDialog
        open={proxyPoolDialogOpen}
        proxies={proxyPool.proxies}
        onClose={() => setProxyPoolDialogOpen(false)}
        onCreateProxy={proxyPool.createProxy}
        onUpdateProxy={proxyPool.updateProxy}
        onDeleteProxy={proxyPool.deleteProxy}
        onTestProxy={proxyPool.testProxy}
        onBatchImport={proxyPool.batchImport}
      />
    </section>
  );
}
