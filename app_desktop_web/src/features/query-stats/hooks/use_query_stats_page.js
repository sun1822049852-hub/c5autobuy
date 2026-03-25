import { useEffect, useRef, useState } from "react";

import { buildErrorDisplay } from "../../../shared/feedback_details.js";
import {
  applyRangeModeDefaults,
  buildStatsRequestParams,
  createInitialStatsFilters,
  validateStatsFilters,
} from "../../stats/stats_shared.js";


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
    try {
      const response = await client.getQueryItemStats(buildStatsRequestParams(nextFilters));
      setRows(normalizeQueryStatsResponse(response).items);
      setLoadError(null);
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
