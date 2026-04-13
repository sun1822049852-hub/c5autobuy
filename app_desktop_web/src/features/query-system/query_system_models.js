export const ALL_MODES = ["new_api", "fast_api", "token"];


export function parseNumericValue(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }

  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : null;
}


export function parseAllocationValue(value) {
  if (value === "" || value === null || value === undefined) {
    return 0;
  }

  const nextValue = Number(value);
  if (!Number.isFinite(nextValue)) {
    return 0;
  }
  return Math.max(0, Math.trunc(nextValue));
}


export function toModeAllocationMap(modeAllocations) {
  const normalized = Object.fromEntries(ALL_MODES.map((modeType) => [modeType, 0]));

  for (const allocation of modeAllocations || []) {
    if (!allocation || !ALL_MODES.includes(allocation.mode_type)) {
      continue;
    }
    normalized[allocation.mode_type] = parseAllocationValue(allocation.target_dedicated_count);
  }

  return normalized;
}


export function toModeAllocationList(modeAllocationMap) {
  return ALL_MODES.map((modeType) => ({
    mode_type: modeType,
    target_dedicated_count: parseAllocationValue(modeAllocationMap[modeType]),
  }));
}


export function normalizeItem(item) {
  const modeAllocationMap = toModeAllocationMap(item.mode_allocations);

  return {
    ...item,
    detail_min_wear: item.detail_min_wear ?? item.min_wear ?? null,
    detail_max_wear: item.detail_max_wear ?? item.max_wear ?? null,
    mode_allocations: toModeAllocationList(modeAllocationMap),
  };
}


export function normalizeConfig(config) {
  return {
    ...config,
    items: (config.items || []).map(normalizeItem),
  };
}


export function createBlankItemDraft() {
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


export function createItemDraftFromItem(item) {
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


export function getItemTarget(item, modeType) {
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

  const runtimeTarget = parseAllocationValue(runtimeMode?.target_dedicated_count ?? target);
  if (runtimeMode && runtimeTarget !== target) {
    return {
      mode_type: modeType,
      target_dedicated_count: target,
      actual_dedicated_count: 0,
      status: target > 0 ? "no_capacity" : "shared",
      status_message: target > 0 ? `无可用账号 0/${target}` : "共享中",
    };
  }

  if (runtimeMode) {
    return {
      mode_type: runtimeMode.mode_type || modeType,
      target_dedicated_count: runtimeTarget,
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


export function buildStatusByMode(item, runtimeRow) {
  return Object.fromEntries(ALL_MODES.map((modeType) => [
    modeType,
    buildModeStatus(item, modeType, runtimeRow?.modes?.[modeType]),
  ]));
}


export function buildRuntimeItemMap(runtimeStatus, configId) {
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


export function buildRemainingByMode(items, currentItemId, draft, capacityModes) {
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


export function buildViewItem(item, _items, runtimeItemMap) {
  const runtimeRow = runtimeItemMap[item.query_item_id];

  return {
    ...item,
    modeTargets: toModeAllocationMap(item.mode_allocations),
    statusByMode: buildStatusByMode(item, runtimeRow),
  };
}


export function isRuntimeWaitingForConfig(runtimeStatus, configId) {
  return Boolean(configId)
    && runtimeStatus.config_id === configId
    && !runtimeStatus.running
    && String(runtimeStatus.message || "") === "等待购买账号恢复";
}


export function isRuntimeRunningForConfig(runtimeStatus, configId) {
  return Boolean(configId)
    && runtimeStatus.config_id === configId
    && Boolean(runtimeStatus.running);
}


export function getConfigStatusText({
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


export function validateDraftConfig(draftConfig, capacityModes) {
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


export function serializeItemPayload(item, { includeProductUrl = false } = {}) {
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


export function upsertConfigSummary(configs, nextConfig) {
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


export function applyDraftToItem(item, draft) {
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
