import { useEffect, useMemo, useRef, useState } from "react";


const ALL_MODES = ["new_api", "fast_api", "token"];

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


function parseNumericValue(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }

  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : null;
}


function parseAllocationValue(value) {
  if (value === "" || value === null || value === undefined) {
    return 0;
  }

  const nextValue = Number(value);
  if (!Number.isFinite(nextValue)) {
    return 0;
  }
  return Math.max(0, Math.trunc(nextValue));
}


function toModeAllocationMap(modeAllocations) {
  const normalized = Object.fromEntries(ALL_MODES.map((modeType) => [modeType, 0]));

  for (const allocation of modeAllocations || []) {
    if (!allocation || !ALL_MODES.includes(allocation.mode_type)) {
      continue;
    }
    normalized[allocation.mode_type] = parseAllocationValue(allocation.target_dedicated_count);
  }

  return normalized;
}


function toModeAllocationList(modeAllocationMap) {
  return ALL_MODES.map((modeType) => ({
    mode_type: modeType,
    target_dedicated_count: parseAllocationValue(modeAllocationMap[modeType]),
  }));
}


function normalizeItem(item) {
  const modeAllocationMap = toModeAllocationMap(item.mode_allocations);

  return {
    ...item,
    detail_min_wear: item.detail_min_wear ?? item.min_wear ?? null,
    detail_max_wear: item.detail_max_wear ?? item.max_wear ?? null,
    mode_allocations: toModeAllocationList(modeAllocationMap),
  };
}


function normalizeConfig(config) {
  return {
    ...config,
    items: (config.items || []).map(normalizeItem),
  };
}


function createBlankItemDraft() {
  return {
    queryItemId: null,
    productUrl: "",
    loadedProductUrl: "",
    externalItemId: "",
    itemName: "",
    marketHashName: "",
    minWear: "",
    maxWear: "",
    detailMinWear: "",
    detailMaxWear: "",
    maxPrice: "",
    lastMarketPrice: "",
    manualPaused: false,
    modeAllocations: Object.fromEntries(ALL_MODES.map((modeType) => [modeType, 0])),
    isFetching: false,
    fetchError: "",
  };
}


function createItemDraftFromItem(item) {
  return {
    queryItemId: item.query_item_id,
    productUrl: item.product_url,
    loadedProductUrl: item.product_url,
    externalItemId: item.external_item_id,
    itemName: item.item_name || "",
    marketHashName: item.market_hash_name || "",
    minWear: item.min_wear ?? "",
    maxWear: item.max_wear ?? "",
    detailMinWear: item.detail_min_wear ?? item.min_wear ?? "",
    detailMaxWear: item.detail_max_wear ?? item.max_wear ?? "",
    maxPrice: item.max_price ?? "",
    lastMarketPrice: item.last_market_price ?? "",
    manualPaused: Boolean(item.manual_paused),
    modeAllocations: toModeAllocationMap(item.mode_allocations),
    isFetching: false,
    fetchError: "",
  };
}


function getItemTarget(item, modeType) {
  return toModeAllocationMap(item.mode_allocations)[modeType] ?? 0;
}


function buildModeStatus(item, modeType, runtimeMode) {
  const target = getItemTarget(item, modeType);

  if (item.manual_paused) {
    return {
      mode_type: modeType,
      target_dedicated_count: target,
      actual_dedicated_count: 0,
      status: "manual_paused",
      status_message: "手动暂停",
    };
  }

  if (runtimeMode) {
    return {
      mode_type: runtimeMode.mode_type || modeType,
      target_dedicated_count: parseAllocationValue(runtimeMode.target_dedicated_count ?? target),
      actual_dedicated_count: parseAllocationValue(runtimeMode.actual_dedicated_count),
      status: runtimeMode.status || "no_capacity",
      status_message: runtimeMode.status_message || (target > 0 ? `无可用账号 0/${target}` : "无可用账号"),
    };
  }

  return {
    mode_type: modeType,
    target_dedicated_count: target,
    actual_dedicated_count: 0,
    status: "no_capacity",
    status_message: target > 0 ? `无可用账号 0/${target}` : "无可用账号",
  };
}


function buildStatusByMode(item, runtimeRow) {
  return Object.fromEntries(ALL_MODES.map((modeType) => [
    modeType,
    buildModeStatus(item, modeType, runtimeRow?.modes?.[modeType]),
  ]));
}


function buildRuntimeItemMap(runtimeStatus, configId) {
  if (!configId || runtimeStatus.config_id !== configId) {
    return {};
  }

  return Object.fromEntries((runtimeStatus.item_rows || []).map((row) => [row.query_item_id, row]));
}


function buildRemainingEntry(rawRemainingCount, currentValue) {
  const remainingCount = Math.max(rawRemainingCount, 0);
  const overflowCount = currentValue > remainingCount ? currentValue - remainingCount : 0;
  return {
    remainingCount,
    overflowCount,
  };
}


function buildRemainingByMode(items, currentItemId, draft, capacityModes) {
  return Object.fromEntries(ALL_MODES.map((modeType) => {
    const usedByOthers = items.reduce((total, item) => {
      if (item.query_item_id === currentItemId || item.manual_paused) {
        return total;
      }
      return total + getItemTarget(item, modeType);
    }, 0);

    const availableCount = capacityModes[modeType]?.available_account_count ?? 0;
    const currentValue = draft.manualPaused
      ? 0
      : parseAllocationValue(draft.modeAllocations[modeType]);

    return [modeType, buildRemainingEntry(availableCount - usedByOthers, currentValue)];
  }));
}


function buildViewItem(item, items, runtimeItemMap) {
  const runtimeRow = runtimeItemMap[item.query_item_id];

  return {
    ...item,
    modeTargets: toModeAllocationMap(item.mode_allocations),
    statusByMode: buildStatusByMode(item, runtimeRow),
  };
}


function isRuntimeWaitingForConfig(runtimeStatus, configId) {
  return Boolean(configId)
    && runtimeStatus.config_id === configId
    && !runtimeStatus.running
    && String(runtimeStatus.message || "") === "等待购买账号恢复";
}


function isRuntimeRunningForConfig(runtimeStatus, configId) {
  return Boolean(configId)
    && runtimeStatus.config_id === configId
    && Boolean(runtimeStatus.running);
}


function getConfigStatusText({
  configId,
  hasUnsavedChanges = false,
  isCurrentConfig = false,
  runtimeStatus,
  saveError = "",
}) {
  if (isCurrentConfig && saveError) {
    return "校验失败";
  }
  if (isCurrentConfig && hasUnsavedChanges) {
    return "未保存";
  }
  if (isRuntimeWaitingForConfig(runtimeStatus, configId)) {
    return "等待账号";
  }
  if (isRuntimeRunningForConfig(runtimeStatus, configId)) {
    return "运行中";
  }
  return "已停止";
}


function validateDraftConfig(draftConfig, capacityModes) {
  for (const modeType of ALL_MODES) {
    const allocatedCount = (draftConfig.items || []).reduce((total, item) => {
      if (item.manual_paused) {
        return total;
      }
      return total + getItemTarget(item, modeType);
    }, 0);
    const availableCount = capacityModes[modeType]?.available_account_count ?? 0;
    if (allocatedCount > availableCount) {
      return {
        valid: false,
        message: "校验失败，无法保存",
      };
    }
  }

  return {
    valid: true,
    message: "",
  };
}


function serializeItemPayload(item, { includeProductUrl = false } = {}) {
  const modeTargets = toModeAllocationMap(item.mode_allocations);

  const payload = {
    product_url: item.product_url,
    detail_min_wear: parseNumericValue(item.detail_min_wear),
    detail_max_wear: parseNumericValue(item.detail_max_wear),
    max_price: parseNumericValue(item.max_price),
    manual_paused: Boolean(item.manual_paused),
    mode_allocations: Object.fromEntries(
      ALL_MODES.map((modeType) => [modeType, parseAllocationValue(modeTargets[modeType])]),
    ),
  };

  if (!includeProductUrl) {
    delete payload.product_url;
  }

  return payload;
}


function upsertConfigSummary(configs, nextConfig) {
  const nextSummary = {
    ...nextConfig,
    items: nextConfig.items || [],
    mode_settings: nextConfig.mode_settings || [],
  };
  const existingIndex = configs.findIndex((config) => config.config_id === nextSummary.config_id);
  if (existingIndex < 0) {
    return [...configs, nextSummary];
  }

  const nextConfigs = [...configs];
  nextConfigs[existingIndex] = {
    ...nextConfigs[existingIndex],
    ...nextSummary,
  };
  return nextConfigs;
}


function applyDraftToItem(item, draft) {
  return normalizeItem({
    ...item,
    product_url: draft.productUrl,
    external_item_id: draft.externalItemId,
    item_name: draft.itemName,
    market_hash_name: draft.marketHashName,
    min_wear: parseNumericValue(draft.minWear),
    max_wear: parseNumericValue(draft.maxWear),
    detail_min_wear: parseNumericValue(draft.detailMinWear),
    detail_max_wear: parseNumericValue(draft.detailMaxWear),
    max_price: parseNumericValue(draft.maxPrice),
    last_market_price: parseNumericValue(draft.lastMarketPrice),
    manual_paused: Boolean(draft.manualPaused),
    mode_allocations: toModeAllocationList(draft.modeAllocations),
  });
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

        const preferredConfigId = nextRuntimeStatus.config_id || nextConfigs[0]?.config_id || null;
        if (!preferredConfigId) {
          setSelectedConfigId(null);
          setSourceConfig(null);
          setDraftConfig(null);
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
      return;
    }

    const validation = validateDraftConfig(draftConfig, capacityModeMap);
    if (!validation.valid) {
      setSaveError(validation.message);
      return;
    }

    setIsSaving(true);
    setLoadError("");
    setSaveError("");

    try {
      const draftItemIds = new Set((draftConfig.items || []).map((item) => item.query_item_id));
      for (const item of sourceConfig?.items || []) {
        if (!draftItemIds.has(item.query_item_id)) {
          await client.deleteQueryItem(draftConfig.config_id, item.query_item_id);
        }
      }

      for (const item of draftConfig.items || []) {
        if (item.isNew) {
          await client.addQueryItem(
            draftConfig.config_id,
            serializeItemPayload(item, { includeProductUrl: true }),
          );
          continue;
        }

        await client.updateQueryItem(
          draftConfig.config_id,
          item.query_item_id,
          serializeItemPayload(item),
        );
      }

      await refreshConfigList();
      const refreshed = await loadConfigDetail(draftConfig.config_id);
      setConfigs((current) => upsertConfigSummary(current, refreshed));
    } catch (error) {
      setSaveError(toErrorMessage(error));
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
    saveBarMessage: (
      !currentConfig
        ? "请选择或新建一个配置。"
        : isSaving
          ? "正在保存当前配置..."
          : saveError
            ? saveError
            : hasUnsavedChanges
              ? "有未保存修改"
              : "已保存"
    ),
    saveConfig,
    selectConfig,
  };
}
