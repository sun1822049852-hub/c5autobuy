import { useEffect, useRef, useState } from "react";

import { buildErrorDisplay } from "../../../shared/feedback_details.js";
import {
  applyRangeModeDefaults,
  buildStatsRequestParams,
  createInitialStatsFilters,
  validateStatsFilters,
} from "../../stats/stats_shared.js";


/** 数据新鲜度窗口：5 秒内视为有效，不重复拉取 */
const DATA_FRESHNESS_MS = 5_000;

/** 刷新按钮硬节流：1 秒 */
const REFRESH_THROTTLE_MS = 1_000;


function buildFiltersSignature(filters) {
  const params = buildStatsRequestParams(filters);
  return [
    params.rangeMode || "",
    params.date || "",
    params.startDate || "",
    params.endDate || "",
  ].join("|");
}


function normalizeQueryStatsResponse(response) {
  return {
    items: Array.isArray(response?.items)
      ? response.items.map((item) => ({
        external_item_id: String(item?.external_item_id ?? ""),
        item_name: item?.item_name ? String(item.item_name) : "未命名商品",
        query_execution_count: Number(item?.query_execution_count ?? 0),
        matched_product_count: Number(item?.matched_product_count ?? 0),
        purchase_success_count: Number(item?.purchase_success_count ?? 0),
        purchase_failed_count: Number(item?.purchase_failed_count ?? 0),
        source_mode_stats: Array.isArray(item?.source_mode_stats) ? item.source_mode_stats : [],
      })).filter((item) => item.external_item_id)
      : [],
  };
}


export function useQueryStatsPage({ client }) {
  const filtersRef = useRef(null);
  const [filters, setFilters] = useState(() => {
    const initialFilters = createInitialStatsFilters();
    filtersRef.current = initialFilters;
    return initialFilters;
  });
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  /** 上次成功拉取数据的时间戳 */
  const lastFetchTimestampRef = useRef(0);
  /** 上次成功拉取数据对应的筛选签名（用于 freshness gate 去重） */
  const lastFetchSignatureRef = useRef("");
  /** 上次触发刷新的时间戳（节流用） */
  const lastRefreshClickRef = useRef(0);
  /** 上次触发刷新时的筛选签名（节流只针对同一筛选） */
  const lastRefreshSignatureRef = useRef("");

  function updateFilters(nextValue) {
    const nextFilters = typeof nextValue === "function"
      ? nextValue(filtersRef.current)
      : nextValue;
    filtersRef.current = nextFilters;
    setFilters(nextFilters);
    return nextFilters;
  }

  async function loadStats(nextFilters = filters) {
    const validationError = validateStatsFilters(nextFilters);
    if (validationError) {
      setLoadError({
        details: [],
        message: validationError,
      });
      return;
    }

    setIsLoading(true);
    const signature = buildFiltersSignature(nextFilters);
    try {
      const response = await client.getQueryItemStats(buildStatsRequestParams(nextFilters));
      setRows(normalizeQueryStatsResponse(response).items);
      setLoadError(null);
      lastFetchTimestampRef.current = Date.now();
      lastFetchSignatureRef.current = signature;
    } catch (error) {
      setLoadError(buildErrorDisplay(error));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const initialFilters = createInitialStatsFilters();
    updateFilters(initialFilters);
    loadStats(initialFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  return {
    filters,
    isLoading,
    loadError,
    onDismissError() {
      setLoadError(null);
    },
    onDateChange(nextValue) {
      updateFilters((current) => ({
        ...current,
        date: nextValue,
      }));
    },
    onEndDateChange(nextValue) {
      updateFilters((current) => ({
        ...current,
        endDate: nextValue,
      }));
    },
    onRangeModeChange(nextRangeMode) {
      updateFilters((current) => applyRangeModeDefaults(current, nextRangeMode));
    },
    onRefresh() {
      const now = Date.now();
      const signature = buildFiltersSignature(filtersRef.current);

      // 5 秒新鲜度窗口：同一筛选参数的数据尚新，不重复打接口。
      // 切日期/切范围后需要拉新数据，因此签名变化时必须允许刷新。
      if (
        signature
        && signature === lastFetchSignatureRef.current
        && now - lastFetchTimestampRef.current < DATA_FRESHNESS_MS
      ) {
        return Promise.resolve();
      }

      // 1 秒硬节流：防止连续点击
      if (
        signature
        && signature === lastRefreshSignatureRef.current
        && now - lastRefreshClickRef.current < REFRESH_THROTTLE_MS
      ) {
        return Promise.resolve();
      }

      lastRefreshClickRef.current = now;
      lastRefreshSignatureRef.current = signature;
      return loadStats(filtersRef.current);
    },
    onStartDateChange(nextValue) {
      updateFilters((current) => ({
        ...current,
        startDate: nextValue,
      }));
    },
    rows,
  };
}
