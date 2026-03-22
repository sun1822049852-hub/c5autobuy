import { AccountContextMenu } from "./components/account_context_menu.jsx";
import { AccountTable } from "./components/account_table.jsx";
import { OverviewCards } from "./components/overview_cards.jsx";
import { StatusStrip } from "./components/status_strip.jsx";
import { AccountApiKeyDialog } from "./dialogs/account_api_key_dialog.jsx";
import { AccountCreateDialog } from "./dialogs/account_create_dialog.jsx";
import { AccountProxyDialog } from "./dialogs/account_proxy_dialog.jsx";
import { AccountRemarkDialog } from "./dialogs/account_remark_dialog.jsx";
import { LoginDrawer } from "./drawers/login_drawer.jsx";
import { PurchaseConfigDrawer } from "./drawers/purchase_config_drawer.jsx";
import { useAccountCenterPage } from "./hooks/use_account_center_page.js";


export function AccountCenterPage({ bootstrapConfig, client }) {
  const {
    activeFilter,
    apiKeyDialogAccount,
    closeApiKeyDialog,
    closeContextMenu,
    closeCreateDialog,
    closeLoginDrawer,
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
    openNicknameDialog,
    openProxyDialog,
    openPurchaseStatus,
    overviewCards,
    proxyDialogAccount,
    purchaseDrawerState,
    recentError,
    recentLoginTask,
    recentModification,
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

  return (
    <section className="account-page">
      <header className="account-page__hero">
        <div className="account-page__hero-main">
          <div className="account-page__hero-copy">
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
              cards={overviewCards}
              className="overview-grid--compact-row"
              onSelect={setActiveFilter}
            />
          </div>
        </div>
      </header>

      <section className="account-page__toolbar account-page__toolbar--compact">
        <div className="account-page__toolbar-copy">
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

      <StatusStrip
        backendStatus={bootstrapConfig.backendStatus}
        recentError={recentError}
        recentLoginTask={recentLoginTask}
        recentModification={recentModification}
      />

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
      <AccountContextMenu menu={contextMenu} onClose={closeContextMenu} onDelete={deleteAccount} />
    </section>
  );
}
