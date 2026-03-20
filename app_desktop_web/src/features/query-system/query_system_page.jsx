import { QueryConfigCreateDialog } from "./components/query_config_create_dialog.jsx";
import { QueryConfigDeleteDialog } from "./components/query_config_delete_dialog.jsx";
import { QueryConfigNav } from "./components/query_config_nav.jsx";
import { QueryItemCreatePanel } from "./components/query_item_create_panel.jsx";
import { QueryItemEditDialog } from "./components/query_item_edit_dialog.jsx";
import { QueryItemTable } from "./components/query_item_table.jsx";
import { QuerySaveBar } from "./components/query_save_bar.jsx";
import { QueryWorkbenchHeader } from "./components/query_workbench_header.jsx";
import { useQuerySystemPage } from "./hooks/use_query_system_page.js";


export function QuerySystemPage({ bootstrapConfig, client }) {
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
    editDialogRemainingByMode,
    editItemDraft,
    editingItemId,
    isCreateConfigDialogOpen,
    isCreateItemDialogOpen,
    isCreatingConfig,
    isDeletingConfig,
    isLoading,
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
    saveBarMessage,
    saveConfig,
    selectConfig,
    submitCreateConfig,
    updateCreateItemAllocation,
    updateCreateConfigField,
    updateCreateItemField,
    updateEditItemAllocation,
    updateEditItemField,
    applyEditItem,
  } = useQuerySystemPage({ client });

  return (
    <section className="query-system-page">
      <header className="query-system-page__hero">
        <div className="query-system-page__hero-copy">
          <div className="query-system-page__eyebrow">Query System</div>
          <h1 className="query-system-page__title">查询工作台</h1>
          <p className="query-system-page__subtitle">
            在同一块工作台里完成商品编辑、分配草稿与新增商品，后续再继续接运行态轮询细节。
          </p>
        </div>
        <div className="query-system-page__hero-meta">
          <div className="account-page__backend-pill">后端状态：{bootstrapConfig.backendStatus}</div>
        </div>
      </header>

      {loadError ? (
        <section className="query-system-page__error">{loadError}</section>
      ) : null}

      <div className="query-system-page__layout">
        <QueryConfigNav
          configs={configList}
          isCreatingConfig={isCreatingConfig}
          isLoading={isLoading}
          onDeleteConfig={openDeleteConfigDialog}
          onOpenCreateConfigDialog={openCreateConfigDialog}
          onSelectConfig={selectConfig}
        />

        <div className="query-system-page__workbench">
          <QueryWorkbenchHeader
            capacityModes={capacityModes}
            currentConfig={currentConfig}
            currentStatusText={currentStatusText}
            isLoading={isLoading}
            onOpenCreateItemDialog={openCreateItemDialog}
            runtimeMessage={runtimeMessage}
          />

          <div className="query-system-page__editor-grid">
            <QueryItemTable
              items={itemViewModels}
              onEditItem={openEditItemDialog}
            />
          </div>

          <QuerySaveBar
            disabled={saveBarDisabled}
            isSaving={isSaving}
            message={saveBarMessage}
            onSave={saveConfig}
          />
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
