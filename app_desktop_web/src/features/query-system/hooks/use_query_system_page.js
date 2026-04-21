import { useEffect, useMemo, useRef, useState } from "react";

import { useProgramAccessGuard } from "../../../program_access/program_access_provider.jsx";
import { isProgramReadonlyLocked } from "../../../program_access/program_access_readonly.js";
import {
  useApplyQuerySystemServer,
  usePatchQuerySystemDraft,
  usePatchQuerySystemUi,
  useProgramAccess,
  useQuerySystemDraft,
  useQuerySystemServer,
  useQuerySystemServerHydrated,
  useQuerySystemUi,
} from "../../../runtime/use_app_runtime.js";
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

const QUERY_CONFIG_SERVER_SHAPE_SUMMARY = "summary";
const QUERY_CONFIG_SERVER_SHAPE_DETAIL = "detail";
const ACTIVE_SAVE_NOTICE = "新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。";


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}


function areValuesEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}


function resolvePersistedConfigId(configs) {
  const persistedConfigId = readQuerySystemViewState().selectedConfigId;
  if (!persistedConfigId) {
    return null;
  }

  return configs.find((config) => String(config?.config_id || "") === persistedConfigId)?.config_id || null;
}


function normalizeRuntimeStatus(status) {
  return {
    ...EMPTY_RUNTIME_STATUS,
    ...(status || {}),
    item_rows: Array.isArray(status?.item_rows) ? status.item_rows : [],
  };
}


function findConfigById(configs, configId) {
  if (!configId) {
    return null;
  }

  return configs.find((config) => config.config_id === configId) || null;
}


function findDetailedConfigById(configs, configId) {
  const config = findConfigById(configs, configId);
  if (!config || getConfigServerShape(config) !== QUERY_CONFIG_SERVER_SHAPE_DETAIL) {
    return null;
  }
  return config;
}


function getConfigServerShape(config) {
  return config?.serverShape === QUERY_CONFIG_SERVER_SHAPE_DETAIL
    ? QUERY_CONFIG_SERVER_SHAPE_DETAIL
    : QUERY_CONFIG_SERVER_SHAPE_SUMMARY;
}


function normalizeConfigWithServerShape(config, serverShape) {
  return normalizeConfig({
    ...config,
    serverShape,
  });
}


function mergeConfigSummaries(existingConfigs, nextConfigs) {
  const existingById = new Map(existingConfigs.map((config) => [config.config_id, config]));

  return nextConfigs.map((config) => {
    const normalizedConfig = normalizeConfigWithServerShape(config, QUERY_CONFIG_SERVER_SHAPE_SUMMARY);
    const existingConfig = existingById.get(normalizedConfig.config_id);

    if (!existingConfig || getConfigServerShape(existingConfig) !== QUERY_CONFIG_SERVER_SHAPE_DETAIL) {
      return normalizedConfig;
    }

    return {
      ...existingConfig,
      name: normalizedConfig.name,
      description: normalizedConfig.description,
      enabled: normalizedConfig.enabled,
      created_at: normalizedConfig.created_at,
      updated_at: normalizedConfig.updated_at,
    };
  });
}


function upsertServerConfig(configs, nextConfig) {
  const normalizedConfig = normalizeConfigWithServerShape(nextConfig, QUERY_CONFIG_SERVER_SHAPE_DETAIL);

  return upsertConfigSummary(configs, normalizedConfig).map((config) => (
    config.config_id === normalizedConfig.config_id
      ? normalizedConfig
      : config
  ));
}


function buildSyncedDraftConfig(currentDraft, serverConfig) {
  const normalizedServerConfig = normalizeConfig(serverConfig);
  const serverShape = getConfigServerShape(normalizedServerConfig);

  if (!currentDraft) {
    return normalizedServerConfig;
  }

  if (serverShape === QUERY_CONFIG_SERVER_SHAPE_DETAIL) {
    return normalizedServerConfig;
  }

  if (getConfigServerShape(currentDraft) !== QUERY_CONFIG_SERVER_SHAPE_DETAIL) {
    return normalizedServerConfig;
  }

  return {
    ...cloneValue(currentDraft),
    name: normalizedServerConfig.name,
    description: normalizedServerConfig.description,
    enabled: normalizedServerConfig.enabled,
    created_at: normalizedServerConfig.created_at,
    updated_at: normalizedServerConfig.updated_at,
  };
}



export function useQuerySystemPage({ client, isActive = true }) {
  const { runProgramAccessAction } = useProgramAccessGuard();
  const programAccess = useProgramAccess();
  const isReadonlyLocked = isProgramReadonlyLocked(programAccess);
  const queryServer = useQuerySystemServer();
  const queryUi = useQuerySystemUi();
  const queryDraft = useQuerySystemDraft();
  const queryServerHydrated = useQuerySystemServerHydrated();
  const patchQueryUi = usePatchQuerySystemUi();
  const patchQueryDraft = usePatchQuerySystemDraft();
  const applyQuerySystemServer = useApplyQuerySystemServer();

  const configs = queryServer.configs || [];
  const selectedConfigId = queryUi.selectedConfigId || null;
  const draftConfig = queryDraft.currentConfig || null;
  const hasUnsavedChanges = Boolean(queryDraft.hasUnsavedChanges);
  const capacitySummary = queryServer.capacitySummary || { modes: {} };
  const runtimeStatus = normalizeRuntimeStatus(queryServer.runtimeStatus);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saveNotice, setSaveNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [isCreateConfigDialogOpen, setIsCreateConfigDialogOpen] = useState(false);
  const [createConfigForm, setCreateConfigForm] = useState(EMPTY_CONFIG_FORM);
  const [deleteConfigTarget, setDeleteConfigTarget] = useState(null);
  const [isConfigDeleteMode, setIsConfigDeleteMode] = useState(false);

  const [isCreateItemDialogOpen, setIsCreateItemDialogOpen] = useState(false);
  const [createItemDraft, setCreateItemDraft] = useState(createBlankItemDraft);
  const [editingContext, setEditingContext] = useState(null);
  const [isItemDeleteMode, setIsItemDeleteMode] = useState(false);

  const [isCreatingConfig, setIsCreatingConfig] = useState(false);
  const [isDeletingConfig, setIsDeletingConfig] = useState(false);
  const draftCounterRef = useRef(1);

  function writeSelectedConfigId(configId) {
    patchQueryUi({ selectedConfigId: configId });
    writeQuerySystemViewState({ selectedConfigId: configId ? String(configId) : null });
  }

  function resetTransientEditorState() {
    setEditingContext(null);
    setIsCreateItemDialogOpen(false);
    setCreateItemDraft(createBlankItemDraft());
    setIsConfigDeleteMode(false);
    setIsItemDeleteMode(false);
  }

  function applyDraftFromConfig(config, configId = config?.config_id || null) {
    if (!configId || !config) {
      return null;
    }

    const normalizedConfig = normalizeConfig(config);
    writeSelectedConfigId(configId);
    patchQueryDraft({
      currentConfig: cloneValue(normalizedConfig),
      hasUnsavedChanges: false,
    });
    setSaveError("");
    setSaveNotice("");
    resetTransientEditorState();
    return normalizedConfig;
  }

  function clearCurrentConfig() {
    writeSelectedConfigId(null);
    patchQueryDraft({
      currentConfig: null,
      hasUnsavedChanges: false,
    });
    setSaveError("");
    setSaveNotice("");
    resetTransientEditorState();
  }

  async function refreshConfigList() {
    const nextConfigs = mergeConfigSummaries(configs, await client.listQueryConfigs());
    applyQuerySystemServer({ configs: nextConfigs });
    return nextConfigs;
  }

  async function loadConfigDetail(configId, baseConfigs = configs) {
    const detail = normalizeConfigWithServerShape(
      await client.getQueryConfig(configId),
      QUERY_CONFIG_SERVER_SHAPE_DETAIL,
    );
    applyQuerySystemServer({
      configs: upsertServerConfig(baseConfigs, detail),
    });
    applyDraftFromConfig(detail, configId);
    return detail;
  }

  useEffect(() => {
    let active = true;

    async function ensureQueryState() {
      if (!isActive) {
        return;
      }

      setLoadError("");

      if (!queryServerHydrated) {
        setIsLoading(true);

        try {
          const [nextConfigsRaw, nextCapacitySummary, nextRuntimeStatusRaw] = await Promise.all([
            client.listQueryConfigs(),
            client.getQueryCapacitySummary(),
            client.getQueryRuntimeStatus(),
          ]);
          if (!active) {
            return;
          }

          const nextConfigs = mergeConfigSummaries([], nextConfigsRaw);
          const nextRuntimeStatus = normalizeRuntimeStatus(nextRuntimeStatusRaw);
          applyQuerySystemServer({
            configs: nextConfigs,
            capacitySummary: nextCapacitySummary,
            runtimeStatus: nextRuntimeStatus,
          });

          const preferredConfigId = findConfigById(nextConfigs, selectedConfigId)?.config_id
            || resolvePersistedConfigId(nextConfigs)
            || nextRuntimeStatus.config_id
            || nextConfigs[0]?.config_id
            || null;

          if (!preferredConfigId) {
            clearCurrentConfig();
            return;
          }

          await loadConfigDetail(preferredConfigId, nextConfigs);
        } catch (error) {
          if (!active) {
            return;
          }
          setLoadError(toErrorMessage(error));
        } finally {
          if (active) {
            setIsLoading(false);
          }
        }
        return;
      }

      const preferredConfigId = selectedConfigId
        || resolvePersistedConfigId(configs)
        || runtimeStatus.config_id
        || configs[0]?.config_id
        || null;

      if (!preferredConfigId) {
        clearCurrentConfig();
        setIsLoading(false);
        return;
      }

      if (selectedConfigId !== preferredConfigId) {
        writeSelectedConfigId(preferredConfigId);
      }

      if (draftConfig?.config_id === preferredConfigId) {
        const serverConfig = findConfigById(configs, preferredConfigId);

        if (!hasUnsavedChanges && serverConfig) {
          const syncedDraftConfig = buildSyncedDraftConfig(draftConfig, serverConfig);

          if (!areValuesEqual(syncedDraftConfig, draftConfig)) {
            applyDraftFromConfig(syncedDraftConfig, preferredConfigId);
          }
        }
        setIsLoading(false);
        return;
      }

      const cachedDetailConfig = findDetailedConfigById(configs, preferredConfigId);
      if (cachedDetailConfig) {
        applyDraftFromConfig(cachedDetailConfig, preferredConfigId);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);

      try {
        await loadConfigDetail(preferredConfigId);
      } catch (error) {
        if (!active) {
          return;
        }
        setLoadError(toErrorMessage(error));
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    ensureQueryState();

    return () => {
      active = false;
    };
  }, [
    applyQuerySystemServer,
    client,
    configs,
    draftConfig?.config_id,
    hasUnsavedChanges,
    isActive,
    queryServerHydrated,
    runtimeStatus.config_id,
    selectedConfigId,
  ]);

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
  const editingItemId = editingContext?.queryItemId || null;
  const editingItem = useMemo(() => {
    if (!currentConfig || !editingItemId) {
      return null;
    }

    return currentConfig.items.find((item) => item.query_item_id === editingItemId) || null;
  }, [currentConfig, editingItemId]);
  const editingItemViewModel = useMemo(() => {
    if (!editingItem || !currentConfig) {
      return null;
    }

    return buildViewItem(editingItem, currentConfig.items || [], runtimeItemMap);
  }, [currentConfig, editingItem, runtimeItemMap]);

  const createDialogRemainingByMode = useMemo(
    () => buildRemainingByMode(currentConfig?.items || [], null, createItemDraft, capacityModeMap),
    [capacityModeMap, createItemDraft, currentConfig?.items],
  );
  const editDialogRemainingByMode = useMemo(() => {
    if (!editingItem || !currentConfig) {
      return {};
    }
    return buildRemainingByMode(
      currentConfig.items || [],
      editingItemId,
      createItemDraftFromItem(editingItem),
      capacityModeMap,
    );
  }, [capacityModeMap, currentConfig, editingItem, editingItemId]);

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
    if (isReadonlyLocked || !draftConfig) {
      return;
    }

    patchQueryDraft({
      currentConfig: updater(cloneValue(draftConfig)),
      hasUnsavedChanges: true,
    });
    setSaveError("");
    setSaveNotice("");
  }

  async function selectConfig(configId) {
    setLoadError("");

    const cachedDetailConfig = findDetailedConfigById(configs, configId);
    if (cachedDetailConfig) {
      applyDraftFromConfig(cachedDetailConfig, configId);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    try {
      await loadConfigDetail(configId);
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }

  function openCreateConfigDialog() {
    if (isReadonlyLocked) {
      return;
    }

    setCreateConfigForm(EMPTY_CONFIG_FORM);
    setIsCreateConfigDialogOpen(true);
  }

  function closeCreateConfigDialog() {
    setIsCreateConfigDialogOpen(false);
    setCreateConfigForm(EMPTY_CONFIG_FORM);
  }

  function updateCreateConfigField(field, value) {
    if (isReadonlyLocked) {
      return;
    }

    setCreateConfigForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function submitCreateConfig() {
    if (isReadonlyLocked) {
      return;
    }

    const nextName = String(createConfigForm.name || "").trim();
    if (!nextName) {
      return;
    }

    setIsCreatingConfig(true);
    setLoadError("");

    try {
      const created = normalizeConfigWithServerShape(
        await client.createQueryConfig({
          name: nextName,
          description: String(createConfigForm.description || "").trim() || null,
        }),
        QUERY_CONFIG_SERVER_SHAPE_DETAIL,
      );
      const nextConfigs = upsertServerConfig(configs, created);
      applyQuerySystemServer({ configs: nextConfigs });
      await loadConfigDetail(created.config_id, nextConfigs);
      closeCreateConfigDialog();
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsCreatingConfig(false);
    }
  }

  function openDeleteConfigDialog(config) {
    if (isReadonlyLocked) {
      return;
    }

    setDeleteConfigTarget(config);
  }

  function toggleConfigDeleteMode() {
    if (isReadonlyLocked) {
      return;
    }

    setIsConfigDeleteMode((current) => !current);
  }

  function closeDeleteConfigDialog() {
    setDeleteConfigTarget(null);
  }

  async function confirmDeleteConfig() {
    if (isReadonlyLocked || !deleteConfigTarget) {
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
        clearCurrentConfig();
      } else if (selectedConfigId === deletedConfigId) {
        await loadConfigDetail(nextSelectedId, nextConfigs);
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
    if (isReadonlyLocked) {
      return;
    }

    setCreateItemDraft(createBlankItemDraft());
    setIsCreateItemDialogOpen(true);
  }

  function toggleItemDeleteMode() {
    if (isReadonlyLocked) {
      return;
    }

    setIsItemDeleteMode((current) => !current);
  }

  function closeCreateItemDialog() {
    setIsCreateItemDialogOpen(false);
    setCreateItemDraft(createBlankItemDraft());
  }

  function updateCreateItemField(field, value) {
    if (isReadonlyLocked) {
      return;
    }

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
    if (isReadonlyLocked) {
      return;
    }

    setCreateItemDraft((current) => ({
      ...current,
      modeAllocations: {
        ...current.modeAllocations,
        [modeType]: parseAllocationValue(value),
      },
    }));
  }

  async function lookupCreateItemDetail() {
    if (isReadonlyLocked) {
      return;
    }

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
    if (isReadonlyLocked || !currentConfig || !createItemDraft.itemName) {
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

  function updateDraftItem(queryItemId, updater) {
    if (!currentConfig || !queryItemId) {
      return;
    }

    const hasTarget = currentConfig.items.some((item) => item.query_item_id === queryItemId);
    if (!hasTarget) {
      return;
    }

    updateDraftConfig((current) => ({
      ...current,
      items: current.items.map((item) => (
        item.query_item_id === queryItemId
          ? updater(item)
          : item
      )),
    }));
  }

  function updateDraftItemField(queryItemId, field, value) {
    const itemFieldMap = {
      detailMaxWear: "detail_max_wear",
      detailMinWear: "detail_min_wear",
      manualPaused: "manual_paused",
      maxPrice: "max_price",
    };
    const targetField = itemFieldMap[field];

    if (targetField) {
      updateDraftItem(queryItemId, (item) => normalizeItem({
        ...item,
        [targetField]: targetField === "manual_paused" ? Boolean(value) : value,
      }));
      return;
    }

    updateDraftItem(queryItemId, (item) => applyDraftToItem(item, {
      ...createItemDraftFromItem(item),
      [field]: value,
    }));
  }

  function updateDraftItemAllocation(queryItemId, modeType, value) {
    updateDraftItem(queryItemId, (item) => {
      const draft = createItemDraftFromItem(item);
      return applyDraftToItem(item, {
        ...draft,
        modeAllocations: {
          ...draft.modeAllocations,
          [modeType]: parseAllocationValue(value),
        },
      });
    });
  }

  function toggleDraftItemManualPaused(queryItemId) {
    updateDraftItem(queryItemId, (item) => applyDraftToItem(item, {
      ...createItemDraftFromItem(item),
      manualPaused: !item.manual_paused,
    }));
  }

  function openEditItemDialog(nextContext) {
    if (isReadonlyLocked || !currentConfig) {
      return;
    }

    const queryItemId = nextContext?.queryItemId || null;
    const kind = nextContext?.kind || null;
    const modeType = nextContext?.modeType || null;
    const item = currentConfig.items.find((candidate) => candidate.query_item_id === queryItemId);
    if (!item) {
      return;
    }

    if (!["price", "wear", "allocation"].includes(kind)) {
      return;
    }
    if (kind === "allocation" && !ALL_MODES.includes(modeType)) {
      return;
    }

    setEditingContext({
      queryItemId,
      kind,
      modeType: kind === "allocation" ? modeType : null,
    });
  }

  function deleteDraftItem(queryItemId) {
    updateDraftConfig((current) => ({
      ...current,
      items: current.items.filter((item) => item.query_item_id !== queryItemId),
    }));

    if (editingContext?.queryItemId === queryItemId) {
      closeEditItemDialog();
    }
  }

  function closeEditItemDialog() {
    setEditingContext(null);
  }

  function updateEditingItemField(field, value) {
    if (!editingContext?.queryItemId) {
      return;
    }

    updateDraftItemField(editingContext.queryItemId, field, value);
  }

  function updateEditingItemAllocation(modeType, value) {
    if (!editingContext?.queryItemId) {
      return;
    }

    updateDraftItemAllocation(editingContext.queryItemId, modeType, value);
  }

  async function saveConfig() {
    if (isReadonlyLocked || !draftConfig) {
      return false;
    }

    const validation = validateDraftConfig(draftConfig, capacityModeMap);
    if (!validation.valid) {
      setSaveError(validation.message);
      return false;
    }

    const shouldShowActiveSaveNotice = isCurrentConfigRuntimeActive;
    setIsSaving(true);
    setLoadError("");
    setSaveError("");
    setSaveNotice("");

    try {
      await persistQueryConfigDraft({
        client,
        sourceConfig: findConfigById(configs, draftConfig.config_id) || draftConfig,
        draftConfig,
      });
      if (isCurrentConfigRuntimeActive) {
        const nextRuntimeStatus = await runProgramAccessAction(
          () => client.applyQueryRuntimeConfig(draftConfig.config_id),
        );
        applyQuerySystemServer({
          runtimeStatus: normalizeRuntimeStatus(nextRuntimeStatus),
        });
      }

      const nextConfigs = await refreshConfigList();
      await loadConfigDetail(draftConfig.config_id, nextConfigs);
      if (shouldShowActiveSaveNotice) {
        setSaveNotice(ACTIVE_SAVE_NOTICE);
      }
      return true;
    } catch (error) {
      setSaveError(toErrorMessage(error));
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function discardDraftChanges() {
    const sourceConfig = findConfigById(configs, draftConfig?.config_id || selectedConfigId);

    patchQueryDraft({
      currentConfig: sourceConfig ? cloneValue(normalizeConfig(sourceConfig)) : draftConfig,
      hasUnsavedChanges: false,
    });
    setSaveError("");
    setSaveNotice("");
    resetTransientEditorState();
    return true;
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
    editingContext,
    editingItemViewModel,
    hasUnsavedChanges,
    isConfigDeleteMode,
    isCreateConfigDialogOpen,
    isCreateItemDialogOpen,
    isCreatingConfig,
    isCurrentConfigRuntimeActive,
    isDeletingConfig,
    isLoading,
    isItemDeleteMode,
    isReadonlyLocked,
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
    openEditItemDialog,
    closeEditItemDialog,
    updateEditingItemField,
    updateEditingItemAllocation,
    toggleDraftItemManualPaused,
    toggleItemDeleteMode,
    runtimeMessage: runtimeStatus.message || "未运行",
    saveBarDisabled: !currentConfig || isReadonlyLocked || isSaving || !hasUnsavedChanges,
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
    saveBarNotice: saveNotice,
    discardDraftChanges,
    saveConfig,
    selectConfig,
    isActive,
  };
}
