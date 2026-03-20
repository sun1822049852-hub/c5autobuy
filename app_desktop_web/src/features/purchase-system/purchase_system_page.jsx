import { PurchaseAccountTable } from "./components/purchase_account_table.jsx";
import { PurchaseRecentEvents } from "./components/purchase_recent_events.jsx";
import { PurchaseItemPanel } from "./components/purchase_item_panel.jsx";
import { PurchaseRuntimeActions } from "./components/purchase_runtime_actions.jsx";
import { PurchaseRuntimeHeader } from "./components/purchase_runtime_header.jsx";
import { PurchaseRuntimeOverview } from "./components/purchase_runtime_overview.jsx";
import { PurchaseSettingsPanel } from "./components/purchase_settings_panel.jsx";
import { usePurchaseSystemPage } from "./hooks/use_purchase_system_page.js";


export function PurchaseSystemPage({ bootstrapConfig, client }) {
  const {
    accountRows,
    activeQueryConfig,
    actionLabel,
    enabledAccountDraft,
    isActionPending,
    isLoading,
    isSettingsPending,
    itemRows,
    loadError,
    onRuntimeAction,
    onSavePurchaseAccounts,
    onTogglePurchaseAccount,
    queueSize,
    recentEvents,
    runtimeMessage,
    settingsDirty,
    status,
    totalAccountCount,
    totalPurchasedCount,
    activeAccountCount,
  } = usePurchaseSystemPage({ client });

  return (
    <section className="purchase-system-page">
      <header className="purchase-system-page__hero">
        <div className="purchase-system-page__hero-copy">
          <div className="query-system-page__eyebrow">Purchase System</div>
          <h1 className="purchase-system-page__title">购买系统</h1>
          <p className="purchase-system-page__subtitle">
            直接查看当前绑定的查询配置、命中统计和账号购买件数，先把购买运行态闭环落到新桌面 Web。
          </p>
        </div>
        <div className="query-system-page__hero-meta">
          <div className="account-page__backend-pill">后端状态：{bootstrapConfig.backendStatus}</div>
        </div>
      </header>

      {loadError ? (
        <section className="query-system-page__error">{loadError}</section>
      ) : null}

      <PurchaseRuntimeHeader
        activeQueryConfig={activeQueryConfig}
        isLoading={isLoading}
        matchedProductCount={status.matched_product_count}
        purchaseFailedCount={status.purchase_failed_count}
        purchaseSuccessCount={status.purchase_success_count}
        runtimeMessage={runtimeMessage}
      />

      <div className="purchase-system-page__layout">
        <div className="purchase-system-page__main-stack">
          <PurchaseRuntimeOverview
            activeAccountCount={activeAccountCount}
            queueSize={queueSize}
            totalAccountCount={totalAccountCount}
            totalPurchasedCount={totalPurchasedCount}
          />

          <section className="purchase-system-page__items" aria-label="商品统计列表">
            {(itemRows || []).length ? (
              itemRows.map((row) => (
                <PurchaseItemPanel key={row.query_item_id} row={row} />
              ))
            ) : (
              <div className="purchase-system-page__empty">
                当前没有可展示的商品统计。
              </div>
            )}
          </section>

          <PurchaseRecentEvents events={recentEvents} />
        </div>

        <div className="purchase-system-page__side-stack">
          <PurchaseAccountTable rows={accountRows} />
          <PurchaseSettingsPanel
            enabledAccountIds={enabledAccountDraft}
            isPending={isSettingsPending}
            isSaving={settingsDirty}
            onSave={onSavePurchaseAccounts}
            onToggleAccount={onTogglePurchaseAccount}
            rows={accountRows}
          />
          <PurchaseRuntimeActions
            actionLabel={actionLabel}
            isPending={isActionPending}
            onAction={onRuntimeAction}
          />
        </div>
      </div>
    </section>
  );
}
