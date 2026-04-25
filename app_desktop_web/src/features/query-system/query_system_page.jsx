import { useCallback, useEffect, useRef, useState } from "react";

import { QueryConfigCreateDialog } from "./components/query_config_create_dialog.jsx";
import { QueryConfigDeleteDialog } from "./components/query_config_delete_dialog.jsx";
import { QueryConfigNav } from "./components/query_config_nav.jsx";
import { QueryItemCreatePanel } from "./components/query_item_create_panel.jsx";
import { QueryItemEditDialog } from "./components/query_item_edit_dialog.jsx";
import { QueryItemTable } from "./components/query_item_table.jsx";
import { QueryWorkbenchHeader } from "./components/query_workbench_header.jsx";
import { UnsavedChangesDialog } from "../shell/unsaved_changes_dialog.jsx";
import { useQuerySystemPage } from "./hooks/use_query_system_page.js";

const EMPTY_CONFIG_SWITCH_PROMPT = {
  error: "",
  isOpen: false,
  isSaving: false,
  nextConfigId: null,
};


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
    editingContext,
    editingItemViewModel,
    hasUnsavedChanges,
    isConfigDeleteMode,
    isCreateConfigDialogOpen,
    isCreateItemDialogOpen,
    isCreatingConfig,
    isDeletingConfig,
    isLoading,
    isItemDeleteMode,
    isReadonlyLocked,
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
    saveBarNotice,
    saveConfig,
    selectConfig,
    submitCreateConfig,
    updateCreateItemAllocation,
    updateCreateConfigField,
    updateCreateItemField,
    updateEditingItemAllocation,
    updateEditingItemField,
    toggleDraftItemManualPaused,
    toggleConfigDeleteMode,
    toggleItemDeleteMode,
  } = useQuerySystemPage({ client, isActive });
  const saveConfigRef = useRef(saveConfig);
  const discardDraftChangesRef = useRef(discardDraftChanges);
  const selectConfigRef = useRef(selectConfig);
  const [configSwitchPrompt, setConfigSwitchPrompt] = useState(EMPTY_CONFIG_SWITCH_PROMPT);

  saveConfigRef.current = saveConfig;
  discardDraftChangesRef.current = discardDraftChanges;
  selectConfigRef.current = selectConfig;

  const canPromptOnConfigSwitch = Boolean(currentConfig) && hasUnsavedChanges;

  const resetConfigSwitchPrompt = useCallback(() => {
    setConfigSwitchPrompt(EMPTY_CONFIG_SWITCH_PROMPT);
  }, []);

  const handleSelectConfig = useCallback((nextConfigId) => {
    if (!nextConfigId || nextConfigId === currentConfig?.config_id) {
      return;
    }

    if (canPromptOnConfigSwitch) {
      setConfigSwitchPrompt({
        error: "",
        isOpen: true,
        isSaving: false,
        nextConfigId,
      });
      return;
    }

    void selectConfigRef.current(nextConfigId);
  }, [canPromptOnConfigSwitch, currentConfig?.config_id]);

  const handleDiscardAndSwitchConfig = useCallback(async () => {
    if (!configSwitchPrompt.nextConfigId) {
      return;
    }

    const discarded = await discardDraftChangesRef.current();
    if (!discarded) {
      return;
    }

    const nextConfigId = configSwitchPrompt.nextConfigId;
    resetConfigSwitchPrompt();
    await selectConfigRef.current(nextConfigId);
  }, [configSwitchPrompt.nextConfigId, resetConfigSwitchPrompt]);

  const handleSaveAndSwitchConfig = useCallback(async () => {
    if (!configSwitchPrompt.nextConfigId) {
      return;
    }

    setConfigSwitchPrompt((current) => ({
      ...current,
      error: "",
      isSaving: true,
    }));

    const nextConfigId = configSwitchPrompt.nextConfigId;
    const saved = await saveConfigRef.current();
    if (!saved) {
      setConfigSwitchPrompt((current) => ({
        ...current,
        error: "保存失败，请先修复后再切换。",
        isSaving: false,
      }));
      return;
    }

    resetConfigSwitchPrompt();
    await selectConfigRef.current(nextConfigId);
  }, [configSwitchPrompt.nextConfigId, resetConfigSwitchPrompt]);

  useEffect(() => {
    onLeaveStateChange?.({
      canPromptOnLeave: Boolean(currentConfig) && hasUnsavedChanges,
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
  }, [currentConfig, hasUnsavedChanges, onLeaveStateChange]);

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
          mutationsDisabled={isReadonlyLocked}
          onDeleteConfig={openDeleteConfigDialog}
          onOpenCreateConfigDialog={openCreateConfigDialog}
          onSelectConfig={handleSelectConfig}
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
            saveNotice={saveBarNotice}
          />

          <div className="query-system-page__editor-grid">
            <QueryItemTable
              canManageItems={Boolean(currentConfig) && !isReadonlyLocked}
              isDeleteMode={isItemDeleteMode}
              items={itemViewModels}
              readOnly={isReadonlyLocked}
              onDeleteItem={deleteDraftItem}
              onEditItem={openEditItemDialog}
              onToggleManualPause={toggleDraftItemManualPaused}
              onOpenCreateItemDialog={openCreateItemDialog}
              onToggleDeleteMode={toggleItemDeleteMode}
            />
          </div>
        </div>
      </div>

      <QueryConfigCreateDialog
        form={createConfigForm}
        isOpen={isCreateConfigDialogOpen}
        isReadonly={isReadonlyLocked}
        isSubmitting={isCreatingConfig}
        onClose={closeCreateConfigDialog}
        onFieldChange={updateCreateConfigField}
        onSubmit={submitCreateConfig}
      />

      <QueryConfigDeleteDialog
        config={deleteConfigTarget}
        isDeleting={isDeletingConfig}
        isReadonly={isReadonlyLocked}
        onClose={closeDeleteConfigDialog}
        onConfirm={confirmDeleteConfig}
      />

      <QueryItemCreatePanel
        draft={createItemDraft}
        isOpen={isCreateItemDialogOpen}
        isReadonly={isReadonlyLocked}
        onAdd={addDraftItem}
        onAllocationChange={updateCreateItemAllocation}
        onClose={closeCreateItemDialog}
        onFieldChange={updateCreateItemField}
        onLookup={lookupCreateItemDetail}
        remainingByMode={createDialogRemainingByMode}
      />

      <QueryItemEditDialog
        context={editingContext}
        item={editingItemViewModel}
        isOpen={Boolean(editingContext)}
        onAllocationChange={updateEditingItemAllocation}
        onClose={closeEditItemDialog}
        onFieldChange={updateEditingItemField}
        remainingByMode={editDialogRemainingByMode}
      />

      <UnsavedChangesDialog
        error={configSwitchPrompt.error}
        isOpen={configSwitchPrompt.isOpen}
        isSaving={configSwitchPrompt.isSaving}
        onDiscard={handleDiscardAndSwitchConfig}
        onSave={handleSaveAndSwitchConfig}
      />
    </section>
  );
}
