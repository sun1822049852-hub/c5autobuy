import { useEffect, useMemo, useState } from "react";

import { useFloatingRuntimeModalState } from "./use_floating_runtime_modal_state.js";


const ALL_MODES = ["new_api", "fast_api", "token"];

const EMPTY_STATUS = {
  running: false,
  message: "未运行",
  queue_size: 0,
  active_account_count: 0,
  total_account_count: 0,
  total_purchased_count: 0,
  active_query_config: null,
  matched_product_count: 0,
  purchase_success_count: 0,
  purchase_failed_count: 0,
  recent_events: [],
  accounts: [],
  item_rows: [],
};

const EMPTY_CAPACITY_SUMMARY = {
  modes: {},
};


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
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


function normalizeModeStatus(modeStatus, modeType) {
  return {
    mode_type: modeStatus?.mode_type || modeType,
    target_dedicated_count: parseAllocationValue(modeStatus?.target_dedicated_count),
    actual_dedicated_count: parseAllocationValue(modeStatus?.actual_dedicated_count),
    status: modeStatus?.status || "inactive",
    status_message: modeStatus?.status_message || "未运行",
  };
}


function normalizePurchaseItemRow(row) {
  const normalizedModes = {};
  for (const modeType of ALL_MODES) {
    if (row?.modes?.[modeType]) {
      normalizedModes[modeType] = normalizeModeStatus(row.modes[modeType], modeType);
    }
  }

  return {
    query_item_id: String(row?.query_item_id ?? ""),
    item_name: row?.item_name ? String(row.item_name) : null,
    max_price: row?.max_price ?? null,
    min_wear: row?.min_wear ?? null,
    max_wear: row?.max_wear ?? null,
    detail_min_wear: row?.detail_min_wear ?? null,
    detail_max_wear: row?.detail_max_wear ?? null,
    manual_paused: Boolean(row?.manual_paused),
    query_execution_count: Number(row?.query_execution_count ?? 0),
    matched_product_count: Number(row?.matched_product_count ?? 0),
    purchase_success_count: Number(row?.purchase_success_count ?? 0),
    purchase_failed_count: Number(row?.purchase_failed_count ?? 0),
    source_mode_stats: Array.isArray(row?.source_mode_stats) ? row.source_mode_stats : [],
    recent_hit_sources: Array.isArray(row?.recent_hit_sources) ? row.recent_hit_sources : [],
    modes: normalizedModes,
  };
}


function normalizeStatus(status) {
  return {
    ...EMPTY_STATUS,
    ...status,
    active_query_config: status?.active_query_config
      ? {
        config_id: String(status.active_query_config.config_id ?? ""),
        config_name: status.active_query_config.config_name
          ? String(status.active_query_config.config_name)
          : null,
        state: status.active_query_config.state ? String(status.active_query_config.state) : "idle",
        message: status.active_query_config.message ? String(status.active_query_config.message) : "",
      }
      : null,
    recent_events: Array.isArray(status?.recent_events) ? status.recent_events : [],
    accounts: Array.isArray(status?.accounts)
      ? status.accounts.map((account) => ({
        ...account,
        account_id: String(account?.account_id ?? ""),
        display_name: account?.display_name ? String(account.display_name) : null,
        purchase_disabled: Boolean(account?.purchase_disabled),
        selected_inventory_name: account?.selected_inventory_name
          ? String(account.selected_inventory_name)
          : null,
      }))
      : [],
    item_rows: Array.isArray(status?.item_rows)
      ? status.item_rows.map(normalizePurchaseItemRow).filter((row) => row.query_item_id)
      : [],
  };
}


function normalizeConfigList(configs) {
  if (!Array.isArray(configs)) {
    return [];
  }

  return configs.map((config) => ({
    config_id: String(config?.config_id ?? ""),
    name: String(config?.name ?? ""),
    description: config?.description ? String(config.description) : "",
  })).filter((config) => config.config_id && config.name);
}


function normalizeQueryItem(item) {
  return {
    ...item,
    query_item_id: String(item?.query_item_id ?? ""),
    detail_min_wear: item?.detail_min_wear ?? item?.min_wear ?? null,
    detail_max_wear: item?.detail_max_wear ?? item?.max_wear ?? null,
    manual_paused: Boolean(item?.manual_paused),
    mode_allocations: toModeAllocationList(toModeAllocationMap(item?.mode_allocations)),
  };
}


function normalizeQueryConfigDetail(config) {
  if (!config) {
    return null;
  }

  return {
    ...config,
    config_id: String(config.config_id ?? ""),
    name: String(config.name ?? ""),
    description: config.description ? String(config.description) : "",
    items: Array.isArray(config.items)
      ? config.items.map(normalizeQueryItem).filter((item) => item.query_item_id)
      : [],
  };
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


function getConfigById(configs, configId) {
  if (!configId) {
    return null;
  }

  return configs.find((config) => config.config_id === configId) || null;
}


function createItemDraft(item) {
  return {
    manualPaused: Boolean(item?.manual_paused),
    modeAllocations: toModeAllocationMap(item?.mode_allocations),
  };
}


function replaceConfigItem(detail, queryItemId, nextItem) {
  if (!detail) {
    return detail;
  }

  return {
    ...detail,
    items: detail.items.map((item) => (item.query_item_id === queryItemId ? nextItem : item)),
  };
}


function isConfigActive(status, configId) {
  return Boolean(configId) && status.active_query_config?.config_id === configId;
}


function buildRuntimeItemMap(status, configId) {
  if (!isConfigActive(status, configId)) {
    return {};
  }

  return Object.fromEntries((status.item_rows || []).map((row) => [row.query_item_id, row]));
}


function buildModeStatus({ draft, isCurrentConfigActive, modeType, runtimeMode }) {
  const target = parseAllocationValue(draft.modeAllocations[modeType]);

  if (draft.manualPaused) {
    return {
      mode_type: modeType,
      target_dedicated_count: target,
      actual_dedicated_count: 0,
      status: "manual_paused",
      status_message: "手动暂停",
    };
  }

  if (!isCurrentConfigActive) {
    return {
      mode_type: modeType,
      target_dedicated_count: target,
      actual_dedicated_count: 0,
      status: "inactive",
      status_message: "未运行",
    };
  }

  if (runtimeMode) {
    return normalizeModeStatus(
      {
        ...runtimeMode,
        target_dedicated_count: runtimeMode.target_dedicated_count ?? target,
      },
      modeType,
    );
  }

  return {
    mode_type: modeType,
    target_dedicated_count: target,
    actual_dedicated_count: 0,
    status: target > 0 ? "no_capacity" : "shared",
    status_message: target > 0 ? `无可用账号 0/${target}` : "共享中",
  };
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
      return total + toModeAllocationMap(item.mode_allocations)[modeType];
    }, 0);

    const availableCount = capacityModes[modeType]?.available_account_count ?? 0;
    const currentValue = draft.manualPaused ? 0 : parseAllocationValue(draft.modeAllocations[modeType]);

    return [modeType, buildRemainingEntry(availableCount - usedByOthers, currentValue)];
  }));
}


function applyRuntimeMessage(result, fallbackMessage) {
  if (result?.message) {
    return String(result.message);
  }
  if (result?.status === "failed_after_save") {
    return "已保存，但当前运行时未同步成功，请重试应用";
  }
  return fallbackMessage;
}


export function usePurchaseSystemPage({ client }) {
  const [status, setStatus] = useState(EMPTY_STATUS);
  const [configList, setConfigList] = useState([]);
  const [capacitySummary, setCapacitySummary] = useState(EMPTY_CAPACITY_SUMMARY);
  const [selectedConfigId, setSelectedConfigId] = useState(null);
  const [selectedConfigDetail, setSelectedConfigDetail] = useState(null);
  const [selectorDraftId, setSelectorDraftId] = useState(null);
  const [itemDrafts, setItemDrafts] = useState({});
  const [itemSaveStates, setItemSaveStates] = useState({});
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionPending, setIsActionPending] = useState(false);
  const [loadError, setLoadError] = useState("");
  const recentEventsModal = useFloatingRuntimeModalState({
    initialPosition: { x: 96, y: 84 },
    initialSize: { width: 680, height: 420 },
  });
  const accountMonitorModal = useFloatingRuntimeModalState({
    initialPosition: { x: 180, y: 120 },
    initialSize: { width: 860, height: 460 },
  });

  async function refreshStatus({ silent = false } = {}) {
    if (!silent) {
      setIsLoading(true);
    }
    try {
      const nextStatus = await client.getPurchaseRuntimeStatus();
      setStatus(normalizeStatus(nextStatus));
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  }

  async function refreshConfigList() {
    const nextConfigs = await client.listQueryConfigs();
    const normalized = normalizeConfigList(nextConfigs);
    setConfigList(normalized);
    return normalized;
  }

  async function refreshCapacitySummary() {
    const nextCapacitySummary = await client.getQueryCapacitySummary();
    setCapacitySummary(nextCapacitySummary || EMPTY_CAPACITY_SUMMARY);
    return nextCapacitySummary || EMPTY_CAPACITY_SUMMARY;
  }

  async function loadSelectedConfigDetail(configId, { resetItemUi = true } = {}) {
    if (!configId) {
      setSelectedConfigId(null);
      setSelectedConfigDetail(null);
      if (resetItemUi) {
        setItemDrafts({});
        setItemSaveStates({});
      }
      return null;
    }

    const detail = normalizeQueryConfigDetail(await client.getQueryConfig(configId));
    setSelectedConfigId(configId);
    setSelectedConfigDetail(detail);
    if (resetItemUi) {
      setItemDrafts({});
      setItemSaveStates({});
    }
    return detail;
  }

  useEffect(() => {
    let active = true;

    async function loadPage() {
      setIsLoading(true);
      try {
        const [nextStatus, nextConfigs, nextCapacitySummary] = await Promise.all([
          client.getPurchaseRuntimeStatus(),
          client.listQueryConfigs(),
          client.getQueryCapacitySummary(),
        ]);
        if (!active) {
          return;
        }

        const normalizedStatus = normalizeStatus(nextStatus);
        setStatus(normalizedStatus);
        setConfigList(normalizeConfigList(nextConfigs));
        setCapacitySummary(nextCapacitySummary || EMPTY_CAPACITY_SUMMARY);
        setLoadError("");

        const preferredConfigId = normalizedStatus.active_query_config?.config_id || null;
        if (!preferredConfigId) {
          setSelectedConfigId(null);
          setSelectedConfigDetail(null);
          setItemDrafts({});
          setItemSaveStates({});
          return;
        }

        const detail = normalizeQueryConfigDetail(await client.getQueryConfig(preferredConfigId));
        if (!active) {
          return;
        }
        setSelectedConfigId(preferredConfigId);
        setSelectedConfigDetail(detail);
        setItemDrafts({});
        setItemSaveStates({});
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

    loadPage();
    const timerId = window.setInterval(() => {
      if (!active) {
        return;
      }
      refreshStatus({ silent: true });
    }, 1500);

    return () => {
      active = false;
      window.clearInterval(timerId);
    };
  }, [client]);

  useEffect(() => {
    const activeConfigId = status.active_query_config?.config_id || null;
    if (!activeConfigId || selectedConfigDetail?.config_id === activeConfigId) {
      return;
    }

    let cancelled = false;
    client.getQueryConfig(activeConfigId)
      .then((detail) => {
        if (cancelled) {
          return;
        }
        setSelectedConfigId(activeConfigId);
        setSelectedConfigDetail(normalizeQueryConfigDetail(detail));
        setItemDrafts({});
        setItemSaveStates({});
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(toErrorMessage(error));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client, selectedConfigDetail?.config_id, status.active_query_config?.config_id]);

  const activeConfig = status.active_query_config;
  const selectedConfigSummary = useMemo(
    () => getConfigById(configList, selectedConfigId),
    [configList, selectedConfigId],
  );
  const configDisplayName = activeConfig?.config_name
    || selectedConfigDetail?.name
    || selectedConfigSummary?.name
    || "未选择配置";
  const runtimeMessage = activeConfig?.message || status.message || "未运行";
  const isRuntimeRunning = Boolean(status.running);
  const actionLabel = isRuntimeRunning ? "停止扫货" : "开始扫货";
  const configActionLabel = isRuntimeRunning ? "切换配置" : "选择配置";
  const isActionDisabled = isActionPending || (!isRuntimeRunning && !selectedConfigId);
  const dialogActionLabel = isRuntimeRunning ? "切换到该配置" : "使用该配置";
  const runtimeItemMap = useMemo(
    () => buildRuntimeItemMap(status, selectedConfigDetail?.config_id || null),
    [selectedConfigDetail?.config_id, status],
  );
  const itemRows = useMemo(() => {
    if (!selectedConfigDetail) {
      return [];
    }

    const isCurrentConfigActive = isConfigActive(status, selectedConfigDetail.config_id);
    return selectedConfigDetail.items.map((item) => {
      const draft = itemDrafts[item.query_item_id] || createItemDraft(item);
      const runtimeRow = runtimeItemMap[item.query_item_id];
      const statusByMode = Object.fromEntries(ALL_MODES.map((modeType) => ([
        modeType,
        buildModeStatus({
          draft,
          isCurrentConfigActive,
          modeType,
          runtimeMode: runtimeRow?.modes?.[modeType],
        }),
      ])));

      return {
        ...item,
        manual_paused: draft.manualPaused,
        source_mode_stats: runtimeRow?.source_mode_stats || [],
        recent_hit_sources: runtimeRow?.recent_hit_sources || [],
        query_execution_count: runtimeRow?.query_execution_count ?? 0,
        matched_product_count: runtimeRow?.matched_product_count ?? 0,
        purchase_success_count: runtimeRow?.purchase_success_count ?? 0,
        purchase_failed_count: runtimeRow?.purchase_failed_count ?? 0,
        draft,
        remainingByMode: buildRemainingByMode(
          selectedConfigDetail.items,
          item.query_item_id,
          draft,
          capacitySummary.modes || {},
        ),
        statusByMode,
        saveState: itemSaveStates[item.query_item_id] || null,
      };
    });
  }, [capacitySummary.modes, itemDrafts, itemSaveStates, runtimeItemMap, selectedConfigDetail, status]);

  function updateItemDraft(queryItemId, updater) {
    const item = selectedConfigDetail?.items.find((entry) => entry.query_item_id === queryItemId);
    if (!item) {
      return;
    }

    setItemDrafts((current) => {
      const baseDraft = current[queryItemId] || createItemDraft(item);
      return {
        ...current,
        [queryItemId]: updater(baseDraft),
      };
    });
    setItemSaveStates((current) => {
      if (!current[queryItemId]) {
        return current;
      }
      return {
        ...current,
        [queryItemId]: null,
      };
    });
  }

  function onItemAllocationChange(queryItemId, modeType, value) {
    updateItemDraft(queryItemId, (current) => ({
      ...current,
      modeAllocations: {
        ...current.modeAllocations,
        [modeType]: parseAllocationValue(value),
      },
    }));
  }

  function onItemManualPausedChange(queryItemId, value) {
    updateItemDraft(queryItemId, (current) => ({
      ...current,
      manualPaused: Boolean(value),
    }));
  }

  async function onSaveItemAllocation(queryItemId) {
    if (!selectedConfigDetail) {
      return;
    }

    const item = selectedConfigDetail.items.find((entry) => entry.query_item_id === queryItemId);
    if (!item) {
      return;
    }

    const draft = itemDrafts[queryItemId] || createItemDraft(item);
    const remainingByMode = buildRemainingByMode(
      selectedConfigDetail.items,
      queryItemId,
      draft,
      capacitySummary.modes || {},
    );
    const hasOverflow = Object.values(remainingByMode).some((entry) => entry.overflowCount > 0);
    if (hasOverflow) {
      setItemSaveStates((current) => ({
        ...current,
        [queryItemId]: {
          message: "校验失败，无法保存",
          pending: false,
          status: "error",
        },
      }));
      return;
    }

    setItemSaveStates((current) => ({
      ...current,
      [queryItemId]: {
        message: "",
        pending: true,
        status: "pending",
      },
    }));

    const payload = {
      detail_min_wear: item.detail_min_wear,
      detail_max_wear: item.detail_max_wear,
      max_price: item.max_price,
      manual_paused: Boolean(draft.manualPaused),
      mode_allocations: Object.fromEntries(
        ALL_MODES.map((modeType) => [modeType, parseAllocationValue(draft.modeAllocations[modeType])]),
      ),
    };

    try {
      const updatedItem = normalizeQueryItem(
        await client.updateQueryItem(selectedConfigDetail.config_id, queryItemId, payload),
      );
      setSelectedConfigDetail((current) => replaceConfigItem(current, queryItemId, updatedItem));
      setItemDrafts((current) => {
        const nextDrafts = { ...current };
        delete nextDrafts[queryItemId];
        return nextDrafts;
      });

      let applyResult;
      try {
        applyResult = await client.applyQueryItemRuntime(selectedConfigDetail.config_id, queryItemId);
      } catch (error) {
        applyResult = {
          status: "failed_after_save",
          message: applyRuntimeMessage(null, toErrorMessage(error)),
        };
      }

      setItemSaveStates((current) => ({
        ...current,
        [queryItemId]: {
          message: applyRuntimeMessage(
            applyResult,
            "已保存，并已应用到当前运行配置",
          ),
          pending: false,
          status: String(applyResult?.status || "applied"),
        },
      }));

      const [statusResult, detailResult, capacityResult] = await Promise.allSettled([
        client.getPurchaseRuntimeStatus(),
        client.getQueryConfig(selectedConfigDetail.config_id),
        client.getQueryCapacitySummary(),
      ]);

      if (statusResult.status === "fulfilled") {
        setStatus(normalizeStatus(statusResult.value));
      }
      if (detailResult.status === "fulfilled") {
        setSelectedConfigDetail(normalizeQueryConfigDetail(detailResult.value));
      }
      if (capacityResult.status === "fulfilled") {
        setCapacitySummary(capacityResult.value || EMPTY_CAPACITY_SUMMARY);
      }
    } catch (error) {
      setItemSaveStates((current) => ({
        ...current,
        [queryItemId]: {
          message: toErrorMessage(error),
          pending: false,
          status: "error",
        },
      }));
    }
  }

  async function onRuntimeAction() {
    if (!isRuntimeRunning && !selectedConfigId) {
      return;
    }

    setIsActionPending(true);
    try {
      const nextStatus = isRuntimeRunning
        ? await client.stopPurchaseRuntime()
        : await client.startPurchaseRuntime(selectedConfigId);
      setStatus(normalizeStatus(nextStatus));
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsActionPending(false);
    }
  }

  async function openConfigDialog() {
    try {
      const nextConfigs = await refreshConfigList();
      const nextSelectionId = activeConfig?.config_id
        || selectedConfigId
        || nextConfigs[0]?.config_id
        || null;
      setSelectorDraftId(nextSelectionId);
      setIsConfigDialogOpen(true);
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    }
  }

  function closeConfigDialog() {
    if (isActionPending) {
      return;
    }
    setIsConfigDialogOpen(false);
    setSelectorDraftId(null);
  }

  async function confirmConfigSelection() {
    if (!selectorDraftId) {
      return;
    }

    setIsActionPending(true);
    try {
      await loadSelectedConfigDetail(selectorDraftId);

      if (!isRuntimeRunning || selectorDraftId === activeConfig?.config_id) {
        setIsConfigDialogOpen(false);
        setSelectorDraftId(null);
        setLoadError("");
        return;
      }

      const nextStatus = await client.startPurchaseRuntime(selectorDraftId);
      setStatus(normalizeStatus(nextStatus));
      setIsConfigDialogOpen(false);
      setSelectorDraftId(null);
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsActionPending(false);
    }
  }

  return {
    accountRows: status.accounts,
    actionLabel,
    configActionLabel,
    configDisplayName,
    configList,
    dialogActionLabel,
    activeQueryConfig: activeConfig,
    isActionDisabled,
    isActionPending,
    isConfigDialogOpen,
    isLoading,
    isRecentEventsOpen: recentEventsModal.isOpen,
    isAccountMonitorOpen: accountMonitorModal.isOpen,
    itemRows,
    loadError,
    onCloseAccountMonitor: accountMonitorModal.onClose,
    onConfigDialogSelect: setSelectorDraftId,
    onOpenConfigDialog: openConfigDialog,
    onCloseConfigDialog: closeConfigDialog,
    onConfirmConfigDialog: confirmConfigSelection,
    onCloseRecentEvents: recentEventsModal.onClose,
    onOpenAccountDetails: accountMonitorModal.onOpen,
    onOpenRecentEvents: recentEventsModal.onOpen,
    onRuntimeAction,
    onItemAllocationChange,
    onItemManualPausedChange,
    onSaveItemAllocation,
    queueSize: status.queue_size,
    recentEvents: status.recent_events,
    recentEventsModal,
    runtimeMessage,
    runtimeSessionId: status.runtime_session_id || null,
    selectedDialogConfigId: selectorDraftId,
    status,
    totalAccountCount: status.total_account_count,
    totalPurchasedCount: status.total_purchased_count,
    activeAccountCount: status.active_account_count,
    accountMonitorModal,
    refreshCapacitySummary,
    refreshStatus,
  };
}
