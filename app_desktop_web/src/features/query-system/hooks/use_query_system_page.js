import { useEffect, useMemo, useRef, useState } from "react";

import {
  ALL_MODES,
  applyDraftToItem,
  buildRemainingByMode,
  buildRuntimeItemMap,
  buildViewItem,
  createBlankItemDraft,
  createItemDraftFromItem,
  getConfigStatusText,
  isRuntimeRunningForConfig,
  isRuntimeWaitingForConfig,
  normalizeConfig,
  normalizeItem,
  parseAllocationValue,
  parseNumericValue,
  toModeAllocationList,
  upsertConfigSummary,
  validateDraftConfig,
} from "../query_system_models.js";
import { persistQueryConfigDraft } from "../query_system_persistence.js";
import { readQuerySystemViewState, writeQuerySystemViewState } from "../../shell/app_shell_state.js";


const EMPTY_RUNTIME_STATUS = {
  running: false,
  config_id: null,
  config_name: null,
  message: "未运行",
  item_rows: [],
};

const EMPTY_CONFIG_FORM = {
  name: "",
  description: "",
};


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}


function resolvePersistedConfigId(configs) {
  const persistedConfigId = readQuerySystemViewState().selectedConfigId;
  if (!persistedConfigId) {
    return null;
  }

  return configs.find((config) => String(config?.config_id || "") === persistedConfigId)?.config_id || null;
}


export function useQuerySystemPage({ client }) {
  const [configs, setConfigs] = useState([]);
  const [selectedConfigId, setSelectedConfigId] = useState(null);
  const [sourceConfig, setSourceConfig] = useState(null);
  const [draftConfig, setDraftConfig] = useState(null);
  const [capacitySummary, setCapacitySummary] = useState({ modes: {} });
  const [runtimeStatus, setRuntimeStatus] = useState(EMPTY_RUNTIME_STATUS);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [isCreateConfigDialogOpen, setIsCreateConfigDialogOpen] = useState(false);
  const [createConfigForm, setCreateConfigForm] = useState(EMPTY_CONFIG_FORM);
  const [deleteConfigTarget, setDeleteConfigTarget] = useState(null);
  const [isConfigDeleteMode, setIsConfigDeleteMode] = useState(false);

  const [isCreateItemDialogOpen, setIsCreateItemDialogOpen] = useState(false);
  const [createItemDraft, setCreateItemDraft] = useState(createBlankItemDraft);
  const [editingItemId, setEditingItemId] = useState(null);
  const [editItemDraft, setEditItemDraft] = useState(null);
  const [isItemDeleteMode, setIsItemDeleteMode] = useState(false);

  const [isCreatingConfig, setIsCreatingConfig] = useState(false);
  const [isDeletingConfig, setIsDeletingConfig] = useState(false);
  const draftCounterRef = useRef(1);

  async function refreshConfigList() {
    const nextConfigs = await client.listQueryConfigs();
    setConfigs(nextConfigs);
    return nextConfigs;
  }

  async function loadConfigDetail(configId) {
    const detail = await client.getQueryConfig(configId);
    const normalized = normalizeConfig(detail);

    setSourceConfig(normalized);
    setDraftConfig(cloneValue(normalized));
    setSelectedConfigId(configId);
    writeQuerySystemViewState({ selectedConfigId: configId });
    setHasUnsavedChanges(false);
    setSaveError("");
    setEditingItemId(null);
    setEditItemDraft(null);
    setIsCreateItemDialogOpen(false);
    setCreateItemDraft(createBlankItemDraft());
    setIsConfigDeleteMode(false);
    setIsItemDeleteMode(false);

    return normalized;
  }

  useEffect(() => {
    let isMounted = true;

    async function loadPage() {
      setIsLoading(true);
      setLoadError("");

      try {
        const [nextConfigs, nextCapacitySummary, nextRuntimeStatus] = await Promise.all([
          client.listQueryConfigs(),
          client.getQueryCapacitySummary(),
          client.getQueryRuntimeStatus(),
        ]);
        if (!isMounted) {
          return;
        }

        setConfigs(nextConfigs);
        setCapacitySummary(nextCapacitySummary);
        setRuntimeStatus(nextRuntimeStatus);

        const preferredConfigId = resolvePersistedConfigId(nextConfigs)
          || nextRuntimeStatus.config_id
          || nextConfigs[0]?.config_id
          || null;
        if (!preferredConfigId) {
          setSelectedConfigId(null);
          setSourceConfig(null);
          setDraftConfig(null);
          writeQuerySystemViewState({ selectedConfigId: null });
          return;
        }

        await loadConfigDetail(preferredConfigId);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setLoadError(toErrorMessage(error));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadPage();

    return () => {
      isMounted = false;
    };
  }, [client]);

  const capacityModeMap = capacitySummary.modes || {};
  const capacityModes = useMemo(
    () => ALL_MODES
      .map((modeType) => capacityModeMap[modeType])
      .filter(Boolean),
    [capacityModeMap],
  );
  const currentConfig = draftConfig;
  const runtimeItemMap = useMemo(
    () => buildRuntimeItemMap(runtimeStatus, currentConfig?.config_id || null),
    [currentConfig?.config_id, runtimeStatus],
  );

  const itemViewModels = useMemo(() => {
    if (!currentConfig) {
      return [];
    }

    return (currentConfig.items || []).map((item) => buildViewItem(item, currentConfig.items || [], runtimeItemMap));
  }, [currentConfig, runtimeItemMap]);

  const createDialogRemainingByMode = useMemo(
    () => buildRemainingByMode(currentConfig?.items || [], null, createItemDraft, capacityModeMap),
    [capacityModeMap, createItemDraft, currentConfig?.items],
  );
  const editDialogRemainingByMode = useMemo(() => {
    if (!editItemDraft || !currentConfig) {
      return {};
    }
    return buildRemainingByMode(
      currentConfig.items || [],
      editingItemId,
      editItemDraft,
      capacityModeMap,
    );
  }, [capacityModeMap, currentConfig, editItemDraft, editingItemId]);

  const currentStatusText = currentConfig
    ? getConfigStatusText({
      configId: currentConfig.config_id,
      hasUnsavedChanges,
      isCurrentConfig: true,
      runtimeStatus,
      saveError,
    })
    : "未选择配置";

  const configList = useMemo(() => configs.map((config) => ({
    ...config,
    isSelected: config.config_id === selectedConfigId,
    statusText: getConfigStatusText({
      configId: config.config_id,
      hasUnsavedChanges,
      isCurrentConfig: config.config_id === currentConfig?.config_id,
      runtimeStatus,
      saveError,
    }),
  })), [configs, currentConfig?.config_id, hasUnsavedChanges, runtimeStatus, saveError, selectedConfigId]);

  const isCurrentConfigRuntimeActive = Boolean(currentConfig) && (
    isRuntimeRunningForConfig(runtimeStatus, currentConfig?.config_id)
    || isRuntimeWaitingForConfig(runtimeStatus, currentConfig?.config_id)
  );

  function updateDraftConfig(updater) {
    setDraftConfig((current) => {
      if (!current) {
        return current;
      }
      return updater(current);
    });
    setHasUnsavedChanges(true);
    setSaveError("");
  }

  async function selectConfig(configId) {
    setLoadError("");

    try {
      await loadConfigDetail(configId);
    } catch (error) {
      setLoadError(toErrorMessage(error));
    }
  }

  function openCreateConfigDialog() {
    setCreateConfigForm(EMPTY_CONFIG_FORM);
    setIsCreateConfigDialogOpen(true);
  }

  function closeCreateConfigDialog() {
    setIsCreateConfigDialogOpen(false);
    setCreateConfigForm(EMPTY_CONFIG_FORM);
  }

  function updateCreateConfigField(field, value) {
    setCreateConfigForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function submitCreateConfig() {
    const nextName = String(createConfigForm.name || "").trim();
    if (!nextName) {
      return;
    }

    setIsCreatingConfig(true);
    setLoadError("");

    try {
      const created = await client.createQueryConfig({
        name: nextName,
        description: String(createConfigForm.description || "").trim() || null,
      });
      setConfigs((current) => upsertConfigSummary(current, created));
      await loadConfigDetail(created.config_id);
      closeCreateConfigDialog();
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsCreatingConfig(false);
    }
  }

  function openDeleteConfigDialog(config) {
    setDeleteConfigTarget(config);
  }

  function toggleConfigDeleteMode() {
    setIsConfigDeleteMode((current) => !current);
  }

  function closeDeleteConfigDialog() {
    setDeleteConfigTarget(null);
  }

  async function confirmDeleteConfig() {
    if (!deleteConfigTarget) {
      return;
    }

    setIsDeletingConfig(true);
    setLoadError("");

    try {
      const deletedConfigId = deleteConfigTarget.config_id;
      await client.deleteQueryConfig(deletedConfigId);
      const nextConfigs = await refreshConfigList();
      const nextSelectedId = selectedConfigId === deletedConfigId
        ? (nextConfigs[0]?.config_id || null)
        : selectedConfigId;

      if (!nextSelectedId) {
        setSelectedConfigId(null);
        setSourceConfig(null);
        setDraftConfig(null);
        writeQuerySystemViewState({ selectedConfigId: null });
        setHasUnsavedChanges(false);
        setSaveError("");
      } else {
        await loadConfigDetail(nextSelectedId);
      }

      closeDeleteConfigDialog();
      setIsConfigDeleteMode(false);
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsDeletingConfig(false);
    }
  }

  function openCreateItemDialog() {
    setCreateItemDraft(createBlankItemDraft());
    setIsCreateItemDialogOpen(true);
  }

  function toggleItemDeleteMode() {
    setIsItemDeleteMode((current) => !current);
  }

  function closeCreateItemDialog() {
    setIsCreateItemDialogOpen(false);
    setCreateItemDraft(createBlankItemDraft());
  }

  function updateCreateItemField(field, value) {
    setCreateItemDraft((current) => {
      if (field === "productUrl") {
        return {
          ...createBlankItemDraft(),
          productUrl: value,
        };
      }

      return {
        ...current,
        [field]: field === "manualPaused" ? Boolean(value) : value,
      };
    });
  }

  function updateCreateItemAllocation(modeType, value) {
    setCreateItemDraft((current) => ({
      ...current,
      modeAllocations: {
        ...current.modeAllocations,
        [modeType]: parseAllocationValue(value),
      },
    }));
  }

  async function lookupCreateItemDetail() {
    const normalizedUrl = String(createItemDraft.productUrl || "").trim();
    if (!normalizedUrl) {
      return;
    }

    setCreateItemDraft((current) => ({
      ...current,
      isFetching: true,
      fetchError: "",
    }));

    try {
      const parsed = await client.parseQueryItemUrl(normalizedUrl);
      const detail = await client.fetchQueryItemDetail({
        product_url: parsed.product_url,
        external_item_id: parsed.external_item_id,
      });

      setCreateItemDraft((current) => (
        String(current.productUrl || "").trim() !== normalizedUrl
          ? current
          : {
            ...current,
            productUrl: parsed.product_url,
            loadedProductUrl: parsed.product_url,
            externalItemId: parsed.external_item_id,
            itemName: detail.item_name || "",
            marketHashName: detail.market_hash_name || "",
            minWear: detail.min_wear ?? "",
            maxWear: detail.max_wear ?? detail.detail_max_wear ?? "",
            detailMinWear: detail.min_wear ?? "",
            detailMaxWear: detail.max_wear ?? detail.detail_max_wear ?? "",
            maxPrice: detail.last_market_price ?? "",
            lastMarketPrice: detail.last_market_price ?? "",
            isFetching: false,
            fetchError: "",
          }
      ));
    } catch (error) {
      setCreateItemDraft((current) => (
        String(current.productUrl || "").trim() !== normalizedUrl
          ? current
          : {
            ...current,
            isFetching: false,
            fetchError: toErrorMessage(error),
          }
      ));
    }
  }

  function addDraftItem() {
    if (!currentConfig || !createItemDraft.itemName) {
      return;
    }

    const queryItemId = `draft-item-${draftCounterRef.current}`;
    draftCounterRef.current += 1;

    const nextItem = normalizeItem({
      query_item_id: queryItemId,
      config_id: currentConfig.config_id,
      product_url: createItemDraft.productUrl,
      external_item_id: createItemDraft.externalItemId,
      item_name: createItemDraft.itemName,
      market_hash_name: createItemDraft.marketHashName,
      min_wear: parseNumericValue(createItemDraft.minWear),
      max_wear: parseNumericValue(createItemDraft.maxWear),
      detail_min_wear: parseNumericValue(createItemDraft.detailMinWear),
      detail_max_wear: parseNumericValue(createItemDraft.detailMaxWear),
      max_price: parseNumericValue(createItemDraft.maxPrice),
      last_market_price: parseNumericValue(createItemDraft.lastMarketPrice),
      last_detail_sync_at: null,
      manual_paused: Boolean(createItemDraft.manualPaused),
      mode_allocations: toModeAllocationList(createItemDraft.modeAllocations),
      sort_order: currentConfig.items.length,
      created_at: "",
      updated_at: "",
      isNew: true,
    });

    updateDraftConfig((current) => ({
      ...current,
      items: [...current.items, nextItem],
    }));
    closeCreateItemDialog();
  }

  function openEditItemDialog(queryItemId) {
    if (!currentConfig) {
      return;
    }
    const item = currentConfig.items.find((candidate) => candidate.query_item_id === queryItemId);
    if (!item) {
      return;
    }
    setEditingItemId(queryItemId);
    setEditItemDraft(createItemDraftFromItem(item));
  }

  function deleteDraftItem(queryItemId) {
    updateDraftConfig((current) => ({
      ...current,
      items: current.items.filter((item) => item.query_item_id !== queryItemId),
    }));

    if (editingItemId === queryItemId) {
      closeEditItemDialog();
    }
  }

  function closeEditItemDialog() {
    setEditingItemId(null);
    setEditItemDraft(null);
  }

  function updateEditItemField(field, value) {
    setEditItemDraft((current) => (
      current
        ? {
          ...current,
          [field]: field === "manualPaused" ? Boolean(value) : value,
        }
        : current
    ));
  }

  function updateEditItemAllocation(modeType, value) {
    setEditItemDraft((current) => (
      current
        ? {
          ...current,
          modeAllocations: {
            ...current.modeAllocations,
            [modeType]: parseAllocationValue(value),
          },
        }
        : current
    ));
  }

  function applyEditItem() {
    if (!editItemDraft || !editingItemId) {
      return;
    }

    updateDraftConfig((current) => ({
      ...current,
      items: current.items.map((item) => (
        item.query_item_id === editingItemId
          ? applyDraftToItem(item, editItemDraft)
          : item
      )),
    }));
    closeEditItemDialog();
  }

  async function saveConfig() {
    if (!draftConfig) {
      return false;
    }

    const validation = validateDraftConfig(draftConfig, capacityModeMap);
    if (!validation.valid) {
      setSaveError(validation.message);
      return false;
    }

    setIsSaving(true);
    setLoadError("");
    setSaveError("");

    try {
      await persistQueryConfigDraft({
        client,
        sourceConfig,
        draftConfig,
      });
      if (isCurrentConfigRuntimeActive) {
        await client.applyQueryRuntimeConfig(draftConfig.config_id);
      }

      await refreshConfigList();
      const refreshed = await loadConfigDetail(draftConfig.config_id);
      setConfigs((current) => upsertConfigSummary(current, refreshed));
      return true;
    } catch (error) {
      setSaveError(toErrorMessage(error));
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  return {
    capacityModes,
    configList,
    createConfigForm,
    createDialogRemainingByMode,
    createItemDraft,
    currentConfig,
    currentStatusText,
    deleteConfigTarget,
    deleteDraftItem,
    editDialogRemainingByMode,
    editItemDraft,
    hasUnsavedChanges,
    isConfigDeleteMode,
    isCreateConfigDialogOpen,
    isCreateItemDialogOpen,
    isCreatingConfig,
    isCurrentConfigRuntimeActive,
    isDeletingConfig,
    isLoading,
    isItemDeleteMode,
    isSaving,
    itemViewModels,
    loadError,
    openCreateConfigDialog,
    closeCreateConfigDialog,
    updateCreateConfigField,
    submitCreateConfig,
    openDeleteConfigDialog,
    closeDeleteConfigDialog,
    confirmDeleteConfig,
    toggleConfigDeleteMode,
    openCreateItemDialog,
    closeCreateItemDialog,
    lookupCreateItemDetail,
    updateCreateItemField,
    updateCreateItemAllocation,
    addDraftItem,
    editingItemId,
    openEditItemDialog,
    closeEditItemDialog,
    updateEditItemField,
    updateEditItemAllocation,
    applyEditItem,
    toggleItemDeleteMode,
    runtimeMessage: runtimeStatus.message || "未运行",
    saveBarDisabled: !currentConfig || isSaving || !hasUnsavedChanges,
    saveBarLabel: (
      !currentConfig
        ? "请选择配置"
        : isSaving
          ? "保存中..."
          : hasUnsavedChanges
            ? "保存到当前配置"
            : "已保存"
    ),
    saveBarError: saveError,
    saveConfig,
    selectConfig,
  };
}
