import { PurchaseAccountMonitorModal } from "./components/purchase_account_monitor_modal.jsx";
import { PurchaseConfigSelectorDialog } from "./components/purchase_config_selector_dialog.jsx";
import { PurchaseItemPanel } from "./components/purchase_item_panel.jsx";
import { PurchaseRecentEventsModal } from "./components/purchase_recent_events_modal.jsx";
import { PurchaseRuntimeActions } from "./components/purchase_runtime_actions.jsx";
import { PurchaseRuntimeHeader } from "./components/purchase_runtime_header.jsx";
import { usePurchaseSystemPage } from "./hooks/use_purchase_system_page.js";

const PREVIEW_ITEM_ROWS = [
  {
    query_item_id: "preview-item-1",
    is_preview: true,
    item_name: "AK-47 | Redline",
    max_price: 123.45,
    min_wear: 0.1,
    max_wear: 0.7,
    detail_min_wear: 0.12,
    detail_max_wear: 0.3,
    query_execution_count: 7,
    matched_product_count: 3,
    purchase_success_count: 1,
    purchase_failed_count: 2,
    source_mode_stats: [
      {
        mode_type: "new_api",
        hit_count: 2,
        last_hit_at: "2026-03-20T10:00:00",
        account_id: "preview-query-a",
        account_display_name: "查询账号A",
      },
      {
        mode_type: "fast_api",
        hit_count: 1,
        last_hit_at: "2026-03-20T10:00:03",
        account_id: "preview-query-b",
        account_display_name: "查询账号B",
      },
    ],
  },
];


export function PurchaseSystemPage({ bootstrapConfig, client }) {
  const {
    activeQueryConfig,
    actionLabel,
    accountMonitorModal,
    accountRows,
    configActionLabel,
    configDisplayName,
    configList,
    dialogActionLabel,
    isActionDisabled,
    isActionPending,
    isAccountMonitorOpen,
    isConfigDialogOpen,
    isLoading,
    isRecentEventsOpen,
    itemRows,
    loadError,
    onCloseAccountMonitor,
    onCloseConfigDialog,
    onCloseRecentEvents,
    onConfigDialogSelect,
    onConfirmConfigDialog,
    onItemAllocationChange,
    onItemManualPausedChange,
    onOpenAccountDetails,
    onOpenConfigDialog,
    onOpenRecentEvents,
    onRuntimeAction,
    onSaveItemAllocation,
    recentEvents,
    recentEventsModal,
    runtimeMessage,
    selectedDialogConfigId,
    totalPurchasedCount,
  } = usePurchaseSystemPage({ client });
  const hasRealItems = (itemRows || []).length > 0;
  const displayRows = hasRealItems ? itemRows : PREVIEW_ITEM_ROWS;

  return (
    <section className="purchase-system-page">
      {loadError ? (
        <section className="query-system-page__error">{loadError}</section>
      ) : null}

      <div className="purchase-system-page__layout">
        <section className="purchase-system-page__items-panel" aria-label="配置商品列表">
          <PurchaseRuntimeHeader
            activeQueryConfig={activeQueryConfig}
            configActionLabel={configActionLabel}
            displayConfigName={configDisplayName}
            isLoading={isLoading}
            onOpenConfigDialog={onOpenConfigDialog}
            runtimeMessage={runtimeMessage}
            totalPurchasedCount={totalPurchasedCount}
          />

          <div className="purchase-system-page__items">
            {displayRows.map((row) => (
              <PurchaseItemPanel
                key={row.query_item_id}
                row={row}
                onAllocationChange={onItemAllocationChange}
                onManualPausedChange={onItemManualPausedChange}
                onSave={onSaveItemAllocation}
              />
            ))}
          </div>
        </section>
      </div>

      <PurchaseRuntimeActions
        actionLabel={actionLabel}
        isActionDisabled={isActionDisabled}
        isPending={isActionPending}
        onAction={onRuntimeAction}
        onOpenAccountDetails={onOpenAccountDetails}
        onOpenRecentEvents={onOpenRecentEvents}
      />

      <PurchaseConfigSelectorDialog
        actionLabel={dialogActionLabel}
        configs={configList}
        isOpen={isConfigDialogOpen}
        isSubmitting={isActionPending}
        onClose={onCloseConfigDialog}
        onConfirm={onConfirmConfigDialog}
        onSelect={onConfigDialogSelect}
        selectedConfigId={selectedDialogConfigId}
      />

      <PurchaseRecentEventsModal
        events={recentEvents}
        isOpen={isRecentEventsOpen}
        onClose={onCloseRecentEvents}
        onPositionChange={recentEventsModal.onPositionChange}
        onSizeChange={recentEventsModal.onSizeChange}
        position={recentEventsModal.position}
        size={recentEventsModal.size}
      />

      <PurchaseAccountMonitorModal
        isOpen={isAccountMonitorOpen}
        onClose={onCloseAccountMonitor}
        onPositionChange={accountMonitorModal.onPositionChange}
        onSizeChange={accountMonitorModal.onSizeChange}
        position={accountMonitorModal.position}
        rows={accountRows}
        size={accountMonitorModal.size}
      />
    </section>
  );
}
