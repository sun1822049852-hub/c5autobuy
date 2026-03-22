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

const EMPTY_UI_PREFERENCES = {
  selected_config_id: null,
  updated_at: null,
};

const EMPTY_CONFIG_LEAVE_PROMPT = {
  error: "",
  isOpen: false,
  isSaving: false,
  nextConfigId: null,
};

const QUERY_SETTINGS_MODE_LABELS = {
  new_api: "new API",
  fast_api: "fast API",
  token: "浏览器 token",
};

const QUERY_SETTINGS_MINIMUMS = {
  new_api: 1,
  fast_api: 0.2,
};


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function formatTimePart(value) {
  return String(Math.max(0, Math.trunc(Number(value) || 0))).padStart(2, "0");
}


function formatTimeValue(hour, minute) {
  return `${formatTimePart(hour)}:${formatTimePart(minute)}`;
}


function parseDecimalInput(value) {
  if (value === "" || value === null || value === undefined) {
    return Number.NaN;
  }
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : Number.NaN;
}


function parseTimeValue(value) {
  const matched = /^(\d{2}):(\d{2})$/.exec(String(value || ""));
  if (!matched) {
    return null;
  }

  const hour = Number(matched[1]);
  const minute = Number(matched[2]);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) {
    return null;
  }
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }
  return { hour, minute };
}


function normalizeQuerySettingsDraft(settings) {
  const modeMap = new Map((settings?.modes || []).map((mode) => [mode?.mode_type, mode]));

  return {
    modes: ALL_MODES.map((modeType) => {
      const mode = modeMap.get(modeType) || {};
      return {
        mode_type: modeType,
        enabled: mode.enabled !== undefined ? Boolean(mode.enabled) : true,
        window_enabled: Boolean(mode.window_enabled),
        start_time: formatTimeValue(mode.start_hour, mode.start_minute),
        end_time: formatTimeValue(mode.end_hour, mode.end_minute),
        base_cooldown_min: String(mode.base_cooldown_min ?? ""),
        base_cooldown_max: String(mode.base_cooldown_max ?? ""),
        item_min_cooldown_seconds: String(mode.item_min_cooldown_seconds ?? "0.5"),
        item_min_cooldown_strategy: String(mode.item_min_cooldown_strategy ?? "divide_by_assigned_count"),
        random_delay_enabled: Boolean(mode.random_delay_enabled),
        random_delay_min: String(mode.random_delay_min ?? "0"),
        random_delay_max: String(mode.random_delay_max ?? "0"),
      };
    }),
    warnings: Array.isArray(settings?.warnings) ? settings.warnings : [],
  };
}


function updateQuerySettingsDraft(currentDraft, modeType, field, value) {
  if (!currentDraft) {
    return currentDraft;
  }

  return {
    ...currentDraft,
    modes: currentDraft.modes.map((mode) => (mode.mode_type === modeType
      ? (() => {
        const nextMode = {
          ...mode,
          [field]: value,
        };

        if (field === "base_cooldown_min") {
          const nextMin = parseDecimalInput(value);
          const currentMax = parseDecimalInput(mode.base_cooldown_max);
          if (Number.isFinite(nextMin) && Number.isFinite(currentMax) && nextMin > currentMax) {
            nextMode.base_cooldown_max = String(nextMin);
          }
        }

        if (field === "random_delay_min") {
          const nextMin = parseDecimalInput(value);
          const currentMax = parseDecimalInput(mode.random_delay_max);
          if (Number.isFinite(nextMin) && Number.isFinite(currentMax) && nextMin > currentMax) {
            nextMode.random_delay_max = String(nextMin);
          }
        }

        return nextMode;
      })()
      : mode)),
  };
}


function validateAndBuildQuerySettingsPayload(draft) {
  if (!draft) {
    return {
      error: "查询设置尚未加载完成。",
      hasTokenRisk: false,
      payload: null,
    };
  }

  const payloadModes = [];
  let hasTokenRisk = false;

  for (const mode of draft.modes || []) {
    const label = QUERY_SETTINGS_MODE_LABELS[mode.mode_type] || mode.mode_type || "查询器";
    const baseCooldownMin = parseDecimalInput(mode.base_cooldown_min);
    const baseCooldownMax = parseDecimalInput(mode.base_cooldown_max);
    const itemMinCooldownSeconds = parseDecimalInput(mode.item_min_cooldown_seconds);
    const itemMinCooldownStrategy = String(mode.item_min_cooldown_strategy || "divide_by_assigned_count");
    if (!Number.isFinite(baseCooldownMin)) {
      return { error: `${label} 基础冷却最小必须填写数值`, hasTokenRisk: false, payload: null };
    }
    if (!Number.isFinite(baseCooldownMax)) {
      return { error: `${label} 基础冷却最大必须填写数值`, hasTokenRisk: false, payload: null };
    }
    if (baseCooldownMax < baseCooldownMin) {
      return { error: `${label} 基础冷却最大不能小于最小值`, hasTokenRisk: false, payload: null };
    }

    const minimum = QUERY_SETTINGS_MINIMUMS[mode.mode_type];
    if (minimum !== undefined && baseCooldownMin < minimum) {
      return { error: `${label} 基础冷却不能低于 ${minimum} 秒`, hasTokenRisk: false, payload: null };
    }
    if (!Number.isFinite(itemMinCooldownSeconds)) {
      return { error: `${label} 商品最小冷却必须填写数值`, hasTokenRisk: false, payload: null };
    }
    if (itemMinCooldownSeconds < 0) {
      return { error: `${label} 商品最小冷却不能为负数`, hasTokenRisk: false, payload: null };
    }
    if (!["fixed", "divide_by_assigned_count"].includes(itemMinCooldownStrategy)) {
      return { error: `${label} 商品冷却策略无效`, hasTokenRisk: false, payload: null };
    }

    let randomDelayMin = 0;
    let randomDelayMax = 0;
    if (mode.random_delay_enabled) {
      randomDelayMin = parseDecimalInput(mode.random_delay_min);
      randomDelayMax = parseDecimalInput(mode.random_delay_max);
      if (!Number.isFinite(randomDelayMin)) {
        return { error: `${label} 随机冷却最小必须填写数值`, hasTokenRisk: false, payload: null };
      }
      if (!Number.isFinite(randomDelayMax)) {
        return { error: `${label} 随机冷却最大必须填写数值`, hasTokenRisk: false, payload: null };
      }
      if (randomDelayMin < 0 || randomDelayMax < 0) {
        return { error: `${label} 随机冷却不能为负数`, hasTokenRisk: false, payload: null };
      }
      if (randomDelayMax < randomDelayMin) {
        return { error: `${label} 随机冷却最大不能小于最小值`, hasTokenRisk: false, payload: null };
      }
    }

    let startHour = 0;
    let startMinute = 0;
    let endHour = 0;
    let endMinute = 0;
    if (mode.window_enabled) {
      const start = parseTimeValue(mode.start_time);
      const end = parseTimeValue(mode.end_time);
      if (!start) {
        return { error: `${label} 开始时间格式必须为 HH:MM`, hasTokenRisk: false, payload: null };
      }
      if (!end) {
        return { error: `${label} 结束时间格式必须为 HH:MM`, hasTokenRisk: false, payload: null };
      }
      startHour = start.hour;
      startMinute = start.minute;
      endHour = end.hour;
      endMinute = end.minute;
    }

    if (mode.mode_type === "token" && (baseCooldownMin < 10 || baseCooldownMax < 10)) {
      hasTokenRisk = true;
    }

    payloadModes.push({
      mode_type: mode.mode_type,
      enabled: Boolean(mode.enabled),
      window_enabled: Boolean(mode.window_enabled),
      start_hour: startHour,
      start_minute: startMinute,
      end_hour: endHour,
      end_minute: endMinute,
      base_cooldown_min: baseCooldownMin,
      base_cooldown_max: baseCooldownMax,
      item_min_cooldown_seconds: itemMinCooldownSeconds,
      item_min_cooldown_strategy: itemMinCooldownStrategy,
      random_delay_enabled: Boolean(mode.random_delay_enabled),
      random_delay_min: randomDelayMin,
      random_delay_max: randomDelayMax,
    });
  }

  return {
    error: "",
    hasTokenRisk,
    payload: {
      modes: payloadModes,
    },
  };
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
    shared_available_count: parseAllocationValue(modeStatus?.shared_available_count),
    status: modeStatus?.status || "inactive",
    status_message: modeStatus?.status_message || "未运行",
  };
}


function normalizePurchaseItemRow(row) {
  const normalizedModes = {};
  for (const modeType of ALL_MODES) {
    normalizedModes[modeType] = normalizeModeStatus(row?.modes?.[modeType], modeType);
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


function normalizeUiPreferences(preferences) {
  return {
    ...EMPTY_UI_PREFERENCES,
    ...preferences,
    selected_config_id: preferences?.selected_config_id
      ? String(preferences.selected_config_id)
      : null,
    updated_at: preferences?.updated_at ? String(preferences.updated_at) : null,
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


function normalizeQueryItem(item) {
  return {
    ...item,
    query_item_id: String(item?.query_item_id ?? ""),
    detail_min_wear: item?.detail_min_wear ?? item?.min_wear ?? null,
    detail_max_wear: item?.detail_max_wear ?? item?.max_wear ?? null,
    manual_paused: Boolean(item?.manual_paused),
    mode_allocations: item?.mode_allocations || [],
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


function getConfigById(configs, configId) {
  if (!configId) {
    return null;
  }

  return configs.find((config) => config.config_id === configId) || null;
}


function resolvePersistedConfigId(configs, preferences) {
  const preferredConfigId = preferences?.selected_config_id || null;
  if (!preferredConfigId) {
    return null;
  }

  return getConfigById(configs, preferredConfigId)?.config_id || null;
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


function buildSharedAvailableByMode(runtimeItemMap) {
  const sharedByMode = Object.fromEntries(ALL_MODES.map((modeType) => [modeType, 0]));

  for (const row of Object.values(runtimeItemMap)) {
    for (const modeType of ALL_MODES) {
      if (!sharedByMode[modeType] && row?.modes?.[modeType]) {
        sharedByMode[modeType] = parseAllocationValue(row.modes[modeType].shared_available_count);
      }
    }
  }

  return sharedByMode;
}


function getBaseActualCount(runtimeItemMap, queryItemId, modeType) {
  return parseAllocationValue(runtimeItemMap[queryItemId]?.modes?.[modeType]?.actual_dedicated_count);
}


function getTargetCount(item, modeType) {
  return parseAllocationValue(toModeAllocationMap(item?.mode_allocations)[modeType]);
}


function getDraftActualCount(manualAllocationDrafts, runtimeItemMap, queryItemId, modeType) {
  const draftValue = manualAllocationDrafts?.[queryItemId]?.[modeType];
  if (draftValue === undefined) {
    return getBaseActualCount(runtimeItemMap, queryItemId, modeType);
  }
  return parseAllocationValue(draftValue);
}


function updateManualAllocationDrafts(currentDrafts, runtimeItemMap, queryItemId, modeType, nextActualCount) {
  const nextDrafts = { ...currentDrafts };
  const baseActualCount = getBaseActualCount(runtimeItemMap, queryItemId, modeType);
  const nextItemDraft = {
    ...(nextDrafts[queryItemId] || {}),
  };

  if (nextActualCount === baseActualCount) {
    delete nextItemDraft[modeType];
  } else {
    nextItemDraft[modeType] = parseAllocationValue(nextActualCount);
  }

  if (!Object.keys(nextItemDraft).length) {
    delete nextDrafts[queryItemId];
    return nextDrafts;
  }

  nextDrafts[queryItemId] = nextItemDraft;
  return nextDrafts;
}


function buildDraftDeltaByMode(items, runtimeItemMap, manualAllocationDrafts) {
  const deltas = Object.fromEntries(ALL_MODES.map((modeType) => [modeType, 0]));

  for (const item of items || []) {
    for (const modeType of ALL_MODES) {
      deltas[modeType] += getDraftActualCount(
        manualAllocationDrafts,
        runtimeItemMap,
        item.query_item_id,
        modeType,
      ) - getBaseActualCount(runtimeItemMap, item.query_item_id, modeType);
    }
  }

  return deltas;
}


function buildDraftPayloadItems(items, runtimeItemMap, manualAllocationDrafts) {
  const payloadItems = [];

  for (const item of items || []) {
    for (const modeType of ALL_MODES) {
      const baseActualCount = getBaseActualCount(runtimeItemMap, item.query_item_id, modeType);
      const draftActualCount = getDraftActualCount(
        manualAllocationDrafts,
        runtimeItemMap,
        item.query_item_id,
        modeType,
      );
      if (draftActualCount === baseActualCount) {
        continue;
      }
      payloadItems.push({
        query_item_id: item.query_item_id,
        mode_type: modeType,
        target_actual_count: draftActualCount,
      });
    }
  }

  return payloadItems;
}


export function usePurchaseSystemPage({ client }) {
  const [status, setStatus] = useState(EMPTY_STATUS);
  const [configList, setConfigList] = useState([]);
  const [selectedConfigId, setSelectedConfigId] = useState(null);
  const [selectedConfigDetail, setSelectedConfigDetail] = useState(null);
  const [selectorDraftId, setSelectorDraftId] = useState(null);
  const [manualAllocationDrafts, setManualAllocationDrafts] = useState({});
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionPending, setIsActionPending] = useState(false);
  const [isSubmittingDrafts, setIsSubmittingDrafts] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [querySettingsDraft, setQuerySettingsDraft] = useState(null);
  const [querySettingsWarnings, setQuerySettingsWarnings] = useState([]);
  const [querySettingsError, setQuerySettingsError] = useState("");
  const [isQuerySettingsOpen, setIsQuerySettingsOpen] = useState(false);
  const [isQuerySettingsLoading, setIsQuerySettingsLoading] = useState(false);
  const [isQuerySettingsSaving, setIsQuerySettingsSaving] = useState(false);
  const [configLeavePrompt, setConfigLeavePrompt] = useState(EMPTY_CONFIG_LEAVE_PROMPT);
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

  async function loadSelectedConfigDetail(configId) {
    if (!configId) {
      setSelectedConfigId(null);
      setSelectedConfigDetail(null);
      setManualAllocationDrafts({});
      return null;
    }

    const detail = normalizeQueryConfigDetail(await client.getQueryConfig(configId));
    setSelectedConfigId(configId);
    setSelectedConfigDetail(detail);
    setManualAllocationDrafts({});
    return detail;
  }

  async function openQuerySettings() {
    setIsQuerySettingsOpen(true);
    setIsQuerySettingsLoading(true);
    setQuerySettingsError("");
    try {
      const nextSettings = await client.getQuerySettings();
      const normalizedDraft = normalizeQuerySettingsDraft(nextSettings);
      setQuerySettingsDraft(normalizedDraft);
      setQuerySettingsWarnings(normalizedDraft.warnings);
    } catch (error) {
      setQuerySettingsError(toErrorMessage(error));
    } finally {
      setIsQuerySettingsLoading(false);
    }
  }

  function closeQuerySettings() {
    if (isQuerySettingsSaving) {
      return;
    }
    setIsQuerySettingsOpen(false);
    setQuerySettingsError("");
  }

  function onQuerySettingsChange(modeType, field, value) {
    setQuerySettingsDraft((currentDraft) => updateQuerySettingsDraft(currentDraft, modeType, field, value));
    setQuerySettingsError("");
  }

  async function onSaveQuerySettings() {
    const nextState = validateAndBuildQuerySettingsPayload(querySettingsDraft);
    if (nextState.error) {
      setQuerySettingsError(nextState.error);
      return false;
    }

    if (nextState.hasTokenRisk) {
      const confirmed = typeof window.confirm === "function"
        ? window.confirm("浏览器查询器基础冷却低于 10 秒，封号风险极高。是否仍然保存？")
        : true;
      if (!confirmed) {
        return false;
      }
    }

    setIsQuerySettingsSaving(true);
    try {
      const savedSettings = await client.updateQuerySettings(nextState.payload);
      const normalizedDraft = normalizeQuerySettingsDraft(savedSettings);
      setQuerySettingsDraft(normalizedDraft);
      setQuerySettingsWarnings(normalizedDraft.warnings);
      setQuerySettingsError("");
      setIsQuerySettingsOpen(false);
      return true;
    } catch (error) {
      setQuerySettingsError(toErrorMessage(error));
      return false;
    } finally {
      setIsQuerySettingsSaving(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function loadPage() {
      setIsLoading(true);
      try {
        const [nextStatus, nextConfigs, nextUiPreferences] = await Promise.all([
          client.getPurchaseRuntimeStatus(),
          client.listQueryConfigs(),
          client.getPurchaseUiPreferences(),
        ]);
        if (!active) {
          return;
        }

        const normalizedStatus = normalizeStatus(nextStatus);
        const normalizedConfigs = normalizeConfigList(nextConfigs);
        const normalizedUiPreferences = normalizeUiPreferences(nextUiPreferences);
        setStatus(normalizedStatus);
        setConfigList(normalizedConfigs);
        setLoadError("");

        const preferredConfigId = resolvePersistedConfigId(normalizedConfigs, normalizedUiPreferences)
          || normalizedStatus.active_query_config?.config_id
          || null;

        if (!preferredConfigId) {
          setSelectedConfigId(null);
          setSelectedConfigDetail(null);
          setManualAllocationDrafts({});
          return;
        }

        const detail = normalizeQueryConfigDetail(await client.getQueryConfig(preferredConfigId));
        if (!active) {
          return;
        }
        setSelectedConfigId(preferredConfigId);
        setSelectedConfigDetail(detail);
        setManualAllocationDrafts({});
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

  const activeConfig = status.active_query_config;
  const selectedConfigSummary = useMemo(
    () => getConfigById(configList, selectedConfigId),
    [configList, selectedConfigId],
  );
  const configDisplayName = selectedConfigDetail?.name
    || selectedConfigSummary?.name
    || "未选择配置";
  const runtimeMessage = activeConfig?.message || status.message || "未运行";
  const isRuntimeRunning = Boolean(status.running);
  const isSelectedConfigRunning = Boolean(selectedConfigDetail?.config_id)
    && isConfigActive(status, selectedConfigDetail.config_id);
  const actionLabel = isRuntimeRunning ? "停止扫货" : "开始扫货";
  const configActionLabel = isRuntimeRunning ? "切换配置" : "选择配置";
  const isActionDisabled = isActionPending || (!isRuntimeRunning && !selectedConfigId);
  const dialogActionLabel = isRuntimeRunning ? "切换到该配置" : "使用该配置";
  const runtimeItemMap = useMemo(
    () => buildRuntimeItemMap(status, selectedConfigDetail?.config_id || null),
    [selectedConfigDetail?.config_id, status],
  );
  const baseSharedAvailableByMode = useMemo(
    () => buildSharedAvailableByMode(runtimeItemMap),
    [runtimeItemMap],
  );
  const draftDeltaByMode = useMemo(
    () => buildDraftDeltaByMode(selectedConfigDetail?.items || [], runtimeItemMap, manualAllocationDrafts),
    [manualAllocationDrafts, runtimeItemMap, selectedConfigDetail?.items],
  );
  const sharedAvailableByMode = useMemo(
    () => Object.fromEntries(ALL_MODES.map((modeType) => ([
      modeType,
      Math.max(0, baseSharedAvailableByMode[modeType] - draftDeltaByMode[modeType]),
    ]))),
    [baseSharedAvailableByMode, draftDeltaByMode],
  );
  const draftPayloadItems = useMemo(
    () => buildDraftPayloadItems(selectedConfigDetail?.items || [], runtimeItemMap, manualAllocationDrafts),
    [manualAllocationDrafts, runtimeItemMap, selectedConfigDetail?.items],
  );
  const hasUnsavedRuntimeDrafts = draftPayloadItems.length > 0;

  const itemRows = useMemo(() => {
    if (!selectedConfigDetail) {
      return [];
    }

    return selectedConfigDetail.items.map((item) => {
      const runtimeRow = runtimeItemMap[item.query_item_id];
      const sourceStats = runtimeRow?.source_mode_stats?.length
        ? runtimeRow.source_mode_stats
        : (runtimeRow?.recent_hit_sources || []);
      const modeRows = MODE_ROWS.map((modeType) => {
        const runtimeMode = normalizeModeStatus(runtimeRow?.modes?.[modeType], modeType);
        const actualCount = isSelectedConfigRunning
          ? getDraftActualCount(manualAllocationDrafts, runtimeItemMap, item.query_item_id, modeType)
          : 0;
        const targetCount = getTargetCount(item, modeType);

        return {
          ...runtimeMode,
          actual_dedicated_count: actualCount,
          target_dedicated_count: targetCount,
          shared_available_count: isSelectedConfigRunning ? sharedAvailableByMode[modeType] : 0,
          can_decrease: isSelectedConfigRunning && actualCount > 0,
          can_increase: isSelectedConfigRunning && sharedAvailableByMode[modeType] > 0,
          is_draft: actualCount !== runtimeMode.actual_dedicated_count,
          status_message: isSelectedConfigRunning ? runtimeMode.status_message : "未运行",
        };
      });

      return {
        ...item,
        source_mode_stats: sourceStats,
        recent_hit_sources: runtimeRow?.recent_hit_sources || [],
        query_execution_count: runtimeRow?.query_execution_count ?? 0,
        matched_product_count: runtimeRow?.matched_product_count ?? 0,
        purchase_success_count: runtimeRow?.purchase_success_count ?? 0,
        purchase_failed_count: runtimeRow?.purchase_failed_count ?? 0,
        mode_rows: modeRows,
      };
    });
  }, [
    isSelectedConfigRunning,
    manualAllocationDrafts,
    runtimeItemMap,
    selectedConfigDetail,
    sharedAvailableByMode,
  ]);

  function adjustManualAllocation(queryItemId, modeType, delta) {
    if (!isSelectedConfigRunning) {
      return;
    }

    const currentActualCount = getDraftActualCount(
      manualAllocationDrafts,
      runtimeItemMap,
      queryItemId,
      modeType,
    );
    if (delta > 0 && sharedAvailableByMode[modeType] < delta) {
      return;
    }

    const nextActualCount = Math.max(0, currentActualCount + delta);
    setManualAllocationDrafts((current) => updateManualAllocationDrafts(
      current,
      runtimeItemMap,
      queryItemId,
      modeType,
      nextActualCount,
    ));
  }

  async function onSubmitRuntimeDrafts() {
    if (!selectedConfigDetail || !isSelectedConfigRunning || !draftPayloadItems.length) {
      return false;
    }

    setIsSubmittingDrafts(true);
    try {
      await client.submitQueryRuntimeManualAllocations(selectedConfigDetail.config_id, {
        items: draftPayloadItems,
      });
      const [nextStatus, nextDetail] = await Promise.all([
        client.getPurchaseRuntimeStatus(),
        client.getQueryConfig(selectedConfigDetail.config_id),
      ]);
      setStatus(normalizeStatus(nextStatus));
      setSelectedConfigDetail(normalizeQueryConfigDetail(nextDetail));
      setManualAllocationDrafts({});
      setLoadError("");
      return true;
    } catch (error) {
      setLoadError(toErrorMessage(error));
      return false;
    } finally {
      setIsSubmittingDrafts(false);
    }
  }

  async function performConfigSelection(nextConfigId) {
    if (!nextConfigId) {
      return false;
    }

    setIsActionPending(true);
    try {
      await client.updatePurchaseUiPreferences(nextConfigId);
      await loadSelectedConfigDetail(nextConfigId);

      if (!isRuntimeRunning || nextConfigId === activeConfig?.config_id) {
        setIsConfigDialogOpen(false);
        setSelectorDraftId(null);
        setLoadError("");
        return true;
      }

      const nextStatus = await client.startPurchaseRuntime(nextConfigId);
      setStatus(normalizeStatus(nextStatus));
      setIsConfigDialogOpen(false);
      setSelectorDraftId(null);
      setLoadError("");
      return true;
    } catch (error) {
      setLoadError(toErrorMessage(error));
      return false;
    } finally {
      setIsActionPending(false);
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
      setManualAllocationDrafts({});
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
      const nextSelectionId = selectedConfigId || nextConfigs[0]?.config_id || null;
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

    if (hasUnsavedRuntimeDrafts && selectorDraftId !== selectedConfigId) {
      setConfigLeavePrompt({
        error: "",
        isOpen: true,
        isSaving: false,
        nextConfigId: selectorDraftId,
      });
      setIsConfigDialogOpen(false);
      setSelectorDraftId(null);
      return;
    }

    await performConfigSelection(selectorDraftId);
  }

  async function confirmSaveBeforeConfigSwitch() {
    if (!configLeavePrompt.nextConfigId) {
      return;
    }

    setConfigLeavePrompt((current) => ({
      ...current,
      error: "",
      isSaving: true,
    }));

    const nextConfigId = configLeavePrompt.nextConfigId;
    const saved = await onSubmitRuntimeDrafts();
    if (!saved) {
      setConfigLeavePrompt((current) => ({
        ...current,
        error: "保存失败，请先修复后再切换配置。",
        isSaving: false,
      }));
      return;
    }

    const switched = await performConfigSelection(nextConfigId);
    if (!switched) {
      setConfigLeavePrompt((current) => ({
        ...current,
        error: "切换失败，请重试。",
        isSaving: false,
      }));
      return;
    }

    setConfigLeavePrompt(EMPTY_CONFIG_LEAVE_PROMPT);
  }

  async function discardBeforeConfigSwitch() {
    if (!configLeavePrompt.nextConfigId) {
      return;
    }

    setConfigLeavePrompt((current) => ({
      ...current,
      error: "",
      isSaving: true,
    }));

    const switched = await performConfigSelection(configLeavePrompt.nextConfigId);
    if (!switched) {
      setConfigLeavePrompt((current) => ({
        ...current,
        error: "切换失败，请重试。",
        isSaving: false,
      }));
      return;
    }

    setConfigLeavePrompt(EMPTY_CONFIG_LEAVE_PROMPT);
  }

  return {
    accountRows: status.accounts,
    actionLabel,
    configActionLabel,
    configDisplayName,
    configList,
    dialogActionLabel,
    activeQueryConfig: activeConfig,
    hasUnsavedRuntimeDrafts,
    isActionDisabled,
    isActionPending,
    isConfigDialogOpen,
    isConfigLeavePromptOpen: configLeavePrompt.isOpen,
    isConfigLeavePromptSaving: configLeavePrompt.isSaving,
    isLoading,
    isQuerySettingsLoading,
    isQuerySettingsOpen,
    isQuerySettingsSaving,
    isRecentEventsOpen: recentEventsModal.isOpen,
    isAccountMonitorOpen: accountMonitorModal.isOpen,
    isSubmitDisabled: !hasUnsavedRuntimeDrafts || !isSelectedConfigRunning || isSubmittingDrafts,
    isSubmittingDrafts,
    itemRows,
    loadError,
    configLeavePromptError: configLeavePrompt.error,
    onCloseAccountMonitor: accountMonitorModal.onClose,
    onCloseConfigDialog: closeConfigDialog,
    onCloseQuerySettings: closeQuerySettings,
    onCloseRecentEvents: recentEventsModal.onClose,
    onConfigDialogSelect: setSelectorDraftId,
    onConfirmConfigDialog: confirmConfigSelection,
    onConfirmDiscardConfigSwitch: discardBeforeConfigSwitch,
    onConfirmSaveConfigSwitch: confirmSaveBeforeConfigSwitch,
    onDecreaseAllocation(queryItemId, modeType) {
      adjustManualAllocation(queryItemId, modeType, -1);
    },
    onIncreaseAllocation(queryItemId, modeType) {
      adjustManualAllocation(queryItemId, modeType, 1);
    },
    onOpenAccountDetails: accountMonitorModal.onOpen,
    onOpenConfigDialog: openConfigDialog,
    onOpenQuerySettings: openQuerySettings,
    onOpenRecentEvents: recentEventsModal.onOpen,
    onQuerySettingsChange,
    onRuntimeAction,
    onSaveQuerySettings,
    onSubmitRuntimeDrafts,
    querySettingsDraft,
    querySettingsError,
    querySettingsWarnings,
    recentEvents: status.recent_events,
    recentEventsModal,
    runtimeMessage,
    selectedDialogConfigId: selectorDraftId,
    status,
    totalAccountCount: status.total_account_count,
    totalPurchasedCount: status.total_purchased_count,
    activeAccountCount: status.active_account_count,
    accountMonitorModal,
    refreshStatus,
  };
}


const MODE_ROWS = ["new_api", "fast_api", "token"];
