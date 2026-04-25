import { useProxyPool } from "../proxy-pool/use_proxy_pool.js";
import { ProxyPoolDialog } from "../proxy-pool/proxy_pool_dialog.jsx";
import { AccountContextMenu } from "./components/account_context_menu.jsx";
import { AccountLogsModal } from "./components/account_logs_modal.jsx";
import { AccountApiKeyDialog } from "./dialogs/account_api_key_dialog.jsx";
import { AccountBrowserProxyDialog } from "./dialogs/account_browser_proxy_dialog.jsx";
import { AccountCreateDialog } from "./dialogs/account_create_dialog.jsx";
import { AccountDeleteDialog } from "./dialogs/account_delete_dialog.jsx";
import { FeatureUnavailableDialog } from "./dialogs/feature_unavailable_dialog.jsx";
import { AccountProxyDialog } from "./dialogs/account_proxy_dialog.jsx";
import { AccountRemarkDialog } from "./dialogs/account_remark_dialog.jsx";
import { LoginDrawer } from "./drawers/login_drawer.jsx";
import { PurchaseConfigDrawer } from "./drawers/purchase_config_drawer.jsx";


export function AccountCenterLazySurfaces({
  accountLogs,
  apiKeyDialogAccount,
  browserProxyDialogAccount,
  client,
  closeApiKeyDialog,
  closeBrowserProxyDialog,
  closeContextMenu,
  closeCreateDialog,
  closeDeleteDialog,
  closeFeatureUnavailableDialog,
  closeLoginDrawer,
  closeProxyDialog,
  closePurchaseDrawer,
  closeRemarkDialog,
  confirmDeleteAccount,
  contextMenu,
  createDialogOpen,
  deleteAccount,
  deleteDialogAccount,
  featureUnavailableDialog,
  isDeletingAccount,
  isLoginTaskStarting,
  isOpeningBindingPage,
  isReadonlyLocked,
  loginDrawerAccount,
  loginTaskSnapshot,
  logsModalState,
  onCloseProxyPoolDialog,
  openAccountOpenApiBindingPage,
  proxyDialogAccount,
  proxyPoolDialogOpen,
  purchaseDrawerState,
  refreshPurchaseConfigInventory,
  remarkDialogAccount,
  startLoginFromDrawer,
  submitApiKey,
  submitBrowserProxy,
  submitCreate,
  submitProxy,
  submitPurchaseConfig,
  submitRemark,
  syncAccountOpenApi,
}) {
  const shouldLoadProxyPool = proxyPoolDialogOpen
    || createDialogOpen
    || Boolean(browserProxyDialogAccount)
    || Boolean(proxyDialogAccount);
  const proxyPool = useProxyPool({ client, enabled: shouldLoadProxyPool });

  return (
    <>
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
        onClose={onCloseProxyPoolDialog}
        onCreateProxy={proxyPool.createProxy}
        onUpdateProxy={proxyPool.updateProxy}
        onDeleteProxy={proxyPool.deleteProxy}
        onTestProxy={proxyPool.testProxy}
        onBatchImport={proxyPool.batchImport}
      />
    </>
  );
}
