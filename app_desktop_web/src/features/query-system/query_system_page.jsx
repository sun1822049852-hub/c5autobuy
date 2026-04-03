import { useEffect, useRef } from "react";

import { QueryConfigCreateDialog } from "./components/query_config_create_dialog.jsx";
import { QueryConfigDeleteDialog } from "./components/query_config_delete_dialog.jsx";
import { QueryConfigNav } from "./components/query_config_nav.jsx";
import { QueryItemCreatePanel } from "./components/query_item_create_panel.jsx";
import { QueryItemEditDialog } from "./components/query_item_edit_dialog.jsx";
import { QueryItemTable } from "./components/query_item_table.jsx";
import { QueryWorkbenchHeader } from "./components/query_workbench_header.jsx";
import { useQuerySystemPage } from "./hooks/use_query_system_page.js";


export function QuerySystemPage({ bootstrapConfig, client, isActive, onLeaveStateChange }) {
  const {
    addDraftItem,
    capacityModes,
    closeCreateConfigDialog,
    closeCreateItemDialog,
    closeDeleteConfigDialog,
    closeEditItemDialog,
    configList,
    confirmDeleteConfig,
    createConfigForm,
    createDialogRemainingByMode,
    createItemDraft,
    currentConfig,
    currentStatusText,
    deleteConfigTarget,
    discardDraftChanges,
    deleteDraftItem,
    editDialogRemainingByMode,
    editItemDraft,
    editingItemId,
    hasUnsavedChanges,
    isConfigDeleteMode,
    isCreateConfigDialogOpen,
    isCreateItemDialogOpen,
    isCreatingConfig,
    isDeletingConfig,
    isLoading,
    isItemDeleteMode,
    isSaving,
    itemViewModels,
    loadError,
    lookupCreateItemDetail,
    openCreateConfigDialog,
    openCreateItemDialog,
    openDeleteConfigDialog,
    openEditItemDialog,
    runtimeMessage,
    saveBarDisabled,
    saveBarError,
    saveBarLabel,
    saveConfig,
    selectConfig,
    submitCreateConfig,
    updateCreateItemAllocation,
    updateCreateConfigField,
    updateCreateItemField,
    updateEditItemAllocation,
    updateEditItemField,
    applyEditItem,
    toggleConfigDeleteMode,
    toggleItemDeleteMode,
  } = useQuerySystemPage({ client, isActive });
  const saveConfigRef = useRef(saveConfig);
  const discardDraftChangesRef = useRef(discardDraftChanges);

  saveConfigRef.current = saveConfig;
  discardDraftChangesRef.current = discardDraftChanges;

  useEffect(() => {
    onLeaveStateChange?.({
      canPromptOnLeave: Boolean(currentConfig) && hasUnsavedChanges && !saveBarError,
      requestDiscard() {
        return discardDraftChangesRef.current();
      },
      requestSave() {
        return saveConfigRef.current();
      },
    });

    return () => {
      onLeaveStateChange?.(null);
    };
  }, [currentConfig, hasUnsavedChanges, onLeaveStateChange, saveBarError]);

  return (
    <section className="query-system-page">
      {loadError ? (
        <section className="query-system-page__error">{loadError}</section>
      ) : null}

      <div className="query-system-page__layout">
        <QueryConfigNav
          configs={configList}
          isDeleteMode={isConfigDeleteMode}
          isCreatingConfig={isCreatingConfig}
          isLoading={isLoading}
          onDeleteConfig={openDeleteConfigDialog}
          onOpenCreateConfigDialog={openCreateConfigDialog}
          onSelectConfig={selectConfig}
          onToggleDeleteMode={toggleConfigDeleteMode}
        />

        <div className="query-system-page__workbench">
          <QueryWorkbenchHeader
            capacityModes={capacityModes}
            currentConfig={currentConfig}
            currentStatusText={currentStatusText}
            hasUnsavedChanges={hasUnsavedChanges}
            isLoading={isLoading}
            isSaving={isSaving}
            onSave={saveConfig}
            runtimeMessage={runtimeMessage}
            saveDisabled={saveBarDisabled}
            saveError={saveBarError}
            saveLabel={saveBarLabel}
          />

          <div className="query-system-page__editor-grid">
            <QueryItemTable
              canManageItems={Boolean(currentConfig)}
              isDeleteMode={isItemDeleteMode}
              items={itemViewModels}
              onDeleteItem={deleteDraftItem}
              onEditItem={openEditItemDialog}
              onOpenCreateItemDialog={openCreateItemDialog}
              onToggleDeleteMode={toggleItemDeleteMode}
            />
          </div>
        </div>
      </div>

      <QueryConfigCreateDialog
        form={createConfigForm}
        isOpen={isCreateConfigDialogOpen}
        isSubmitting={isCreatingConfig}
        onClose={closeCreateConfigDialog}
        onFieldChange={updateCreateConfigField}
        onSubmit={submitCreateConfig}
      />

      <QueryConfigDeleteDialog
        config={deleteConfigTarget}
        isDeleting={isDeletingConfig}
        onClose={closeDeleteConfigDialog}
        onConfirm={confirmDeleteConfig}
      />

      <QueryItemCreatePanel
        draft={createItemDraft}
        isOpen={isCreateItemDialogOpen}
        onAdd={addDraftItem}
        onAllocationChange={updateCreateItemAllocation}
        onClose={closeCreateItemDialog}
        onFieldChange={updateCreateItemField}
        onLookup={lookupCreateItemDetail}
        remainingByMode={createDialogRemainingByMode}
      />

      <QueryItemEditDialog
        draft={editItemDraft}
        isOpen={Boolean(editingItemId)}
        onAllocationChange={updateEditItemAllocation}
        onApply={applyEditItem}
        onClose={closeEditItemDialog}
        onFieldChange={updateEditItemField}
        remainingByMode={editDialogRemainingByMode}
      />
    </section>
  );
}
