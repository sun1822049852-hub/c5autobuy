import { useEffect, useRef } from "react";

import { PurchaseAccountMonitorModal } from "./components/purchase_account_monitor_modal.jsx";
import { PurchaseConfigSelectorDialog } from "./components/purchase_config_selector_dialog.jsx";
import { PurchaseItemPanel } from "./components/purchase_item_panel.jsx";
import { PurchaseSettingsPanel } from "./components/purchase_settings_panel.jsx";
import { QuerySettingsModal } from "./components/query_settings_modal.jsx";
import { PurchaseRuntimeActions } from "./components/purchase_runtime_actions.jsx";
import { PurchaseRuntimeHeader } from "./components/purchase_runtime_header.jsx";
import { usePurchaseSystemPage } from "./hooks/use_purchase_system_page.js";
import { UnsavedChangesDialog } from "../shell/unsaved_changes_dialog.jsx";

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


export function PurchaseSystemPage({ bootstrapConfig, client, isActive, onLeaveStateChange }) {
  const {
    activeQueryConfig,
    actionLabel,
    accountMonitorModal,
    accountRows,
    configLeavePromptError,
    configActionLabel,
    configDisplayName,
    configList,
    dialogActionLabel,
    hasUnsavedRuntimeDrafts,
    isActionDisabled,
    isActionPending,
    isAccountMonitorOpen,
    isConfigDialogOpen,
    isConfigLeavePromptOpen,
    isConfigLeavePromptSaving,
    isLoading,
    isPurchaseSettingsOpen,
    isReadonlyLocked,
    isQuerySettingsLoading,
    isQuerySettingsOpen,
    isQuerySettingsSaving,
    isSubmitDisabled,
    isSubmittingDrafts,
    itemRows,
    loadError,
    onCloseAccountMonitor,
    onCloseConfigDialog,
    onClosePurchaseSettings,
    onConfigDialogSelect,
    onConfirmConfigDialog,
    onConfirmDiscardConfigSwitch,
    onConfirmSaveConfigSwitch,
    onDecreaseAllocation,
    onIncreaseAllocation,
    onOpenAccountDetails,
    onOpenConfigDialog,
    onOpenPurchaseSettings,
    onOpenQuerySettings,
    onCloseQuerySettings,
    onPurchaseSettingsChange,
    onQuerySettingsChange,
    onRuntimeAction,
    onSavePurchaseSettings,
    onSaveQuerySettings,
    onSubmitRuntimeDrafts,
    purchaseSettingsDraft,
    purchaseSettingsError,
    purchaseSettingsNotice,
    isPurchaseSettingsSaving,
    querySettingsDraft,
    querySettingsError,
    querySettingsWarnings,
    runtimeMessage,
    runtimeDrainNotice,
    selectedDialogConfigId,
    totalPurchasedCount,
    discardRuntimeDrafts,
  } = usePurchaseSystemPage({ client, isActive });
  const submitRuntimeDraftsRef = useRef(onSubmitRuntimeDrafts);
  const discardRuntimeDraftsRef = useRef(discardRuntimeDrafts);

  submitRuntimeDraftsRef.current = onSubmitRuntimeDrafts;
  discardRuntimeDraftsRef.current = discardRuntimeDrafts;

  useEffect(() => {
    onLeaveStateChange?.({
      canPromptOnLeave: hasUnsavedRuntimeDrafts,
      requestDiscard() {
        return discardRuntimeDraftsRef.current();
      },
      requestSave() {
        return submitRuntimeDraftsRef.current();
      },
    });

    return () => {
      onLeaveStateChange?.(null);
    };
  }, [hasUnsavedRuntimeDrafts, onLeaveStateChange]);
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
            isConfigActionDisabled={isReadonlyLocked}
            isLoading={isLoading}
            isPurchaseSettingsLoading={isPurchaseSettingsSaving}
            isQuerySettingsLoading={isQuerySettingsLoading}
            onOpenConfigDialog={onOpenConfigDialog}
            onOpenPurchaseSettings={onOpenPurchaseSettings}
            onOpenQuerySettings={onOpenQuerySettings}
            runtimeMessage={runtimeMessage}
            runtimeDrainNotice={runtimeDrainNotice}
            totalPurchasedCount={totalPurchasedCount}
          />

          <div className="purchase-system-page__items">
            {displayRows.map((row) => (
              <PurchaseItemPanel
                allocationReadonly={isReadonlyLocked}
                key={row.query_item_id}
                row={row}
                onDecreaseAllocation={onDecreaseAllocation}
                onIncreaseAllocation={onIncreaseAllocation}
              />
            ))}
          </div>
        </section>
      </div>

      <PurchaseRuntimeActions
        actionLabel={actionLabel}
        isActionDisabled={isActionDisabled}
        isPending={isActionPending}
        isSubmitDisabled={isSubmitDisabled}
        isSubmitPending={isSubmittingDrafts}
        onAction={onRuntimeAction}
        onOpenAccountDetails={onOpenAccountDetails}
        onSubmitChanges={onSubmitRuntimeDrafts}
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

      <QuerySettingsModal
        draft={querySettingsDraft}
        error={querySettingsError}
        isLoading={isQuerySettingsLoading}
        isOpen={isQuerySettingsOpen}
        isReadonly={isReadonlyLocked}
        isSaving={isQuerySettingsSaving}
        onChange={onQuerySettingsChange}
        onClose={onCloseQuerySettings}
        onSave={onSaveQuerySettings}
        warnings={querySettingsWarnings}
      />

      {isPurchaseSettingsOpen ? (
        <div
          className="surface-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget && !isPurchaseSettingsSaving) {
              onClosePurchaseSettings?.();
            }
          }}
        >
          <section aria-label="购买设置" className="dialog-surface purchase-settings-modal" role="dialog">
            <div className="surface-header">
              <div>
                <h2 className="surface-title">购买设置</h2>
                <p className="surface-subtitle">控制单批次命中在每个购买 IP 下最多派发多少个当前空闲账号参与购买。</p>
              </div>
              <button
                className="ghost-button"
                disabled={isPurchaseSettingsSaving}
                type="button"
                onClick={onClosePurchaseSettings}
              >
                关闭
              </button>
            </div>

            <PurchaseSettingsPanel
              error={purchaseSettingsError}
              fanoutLimit={purchaseSettingsDraft?.per_batch_ip_fanout_limit || "1"}
              maxInflightPerAccount={purchaseSettingsDraft?.max_inflight_per_account || "3"}
              notice={purchaseSettingsNotice}
              isReadonly={isReadonlyLocked}
              isPending={isPurchaseSettingsSaving}
              isSaving={Boolean(purchaseSettingsDraft?.is_dirty)}
              onFanoutLimitChange={(value) => {
                onPurchaseSettingsChange("per_batch_ip_fanout_limit", value);
              }}
              onMaxInflightPerAccountChange={(value) => {
                onPurchaseSettingsChange("max_inflight_per_account", value);
              }}
              onSave={onSavePurchaseSettings}
            />
          </section>
        </div>
      ) : null}

      <PurchaseAccountMonitorModal
        isOpen={isAccountMonitorOpen}
        onClose={onCloseAccountMonitor}
        onPositionChange={accountMonitorModal.onPositionChange}
        onSizeChange={accountMonitorModal.onSizeChange}
        position={accountMonitorModal.position}
        rows={accountRows}
        size={accountMonitorModal.size}
      />

      <UnsavedChangesDialog
        error={configLeavePromptError}
        isOpen={isConfigLeavePromptOpen}
        isSaving={isConfigLeavePromptSaving}
        onDiscard={onConfirmDiscardConfigSwitch}
        onSave={onConfirmSaveConfigSwitch}
      />
    </section>
  );
}
