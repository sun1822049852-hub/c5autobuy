import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";
import { AccountContextMenu } from "./components/account_context_menu.jsx";
import { AccountLogsModal } from "./components/account_logs_modal.jsx";
import { AccountTable } from "./components/account_table.jsx";
import { OverviewCards } from "./components/overview_cards.jsx";
import { AccountApiKeyDialog } from "./dialogs/account_api_key_dialog.jsx";
import { AccountCreateDialog } from "./dialogs/account_create_dialog.jsx";
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
    closeApiKeyDialog,
    closeContextMenu,
    closeCreateDialog,
    closeLoginDrawer,
    logsModalState,
    closeProxyDialog,
    closePurchaseDrawer,
    closeRemarkDialog,
    contextMenu,
    createDialogOpen,
    deleteAccount,
    filteredRows,
    isLoading,
    loadError,
    loginDrawerAccount,
    openApiKeyDialog,
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
    startLoginFromDrawer,
    submitApiKey,
    submitCreate,
    submitProxy,
    submitPurchaseConfig,
    submitRemark,
    loginTaskSnapshot,
    isLoginTaskStarting,
  } = useAccountCenterPage({ client });
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

  return (
    <section className="account-page">
      <header className="account-page__hero">
        <div className="account-page__hero-main">
          <div className="account-page__hero-copy" style={NO_SELECT_STYLE}>
            <div className="account-page__eyebrow">ACCOUNT CENTER</div>
            <h1 className="account-page__title">
              {isLoading ? "账号中心加载中" : "C5 账号中心"}
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
          <button className="accent-button account-page__toolbar-button" type="button" onClick={openCreateDialog}>
            添加账号
          </button>
        </div>
      </section>

      <section className="account-page__table-panel">
        <AccountTable
          isLoading={isLoading}
          loadError={loadError}
          onApiKeyClick={openApiKeyDialog}
          onNicknameClick={openNicknameDialog}
          onProxyClick={openProxyDialog}
          onPurchaseStatusClick={openPurchaseStatus}
          onRowContextMenu={openContextMenu}
          rows={filteredRows}
        />
      </section>

      <AccountCreateDialog open={createDialogOpen} onClose={closeCreateDialog} onSubmit={submitCreate} />
      <AccountRemarkDialog account={remarkDialogAccount} open={Boolean(remarkDialogAccount)} onClose={closeRemarkDialog} onSubmit={submitRemark} />
      <AccountApiKeyDialog account={apiKeyDialogAccount} open={Boolean(apiKeyDialogAccount)} onClose={closeApiKeyDialog} onSubmit={submitApiKey} />
      <AccountProxyDialog account={proxyDialogAccount} open={Boolean(proxyDialogAccount)} onClose={closeProxyDialog} onSubmit={submitProxy} />
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
      <AccountContextMenu menu={contextMenu} onClose={closeContextMenu} onDelete={deleteAccount} />
    </section>
  );
}
