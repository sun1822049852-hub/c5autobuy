import { useEffect, useRef, useState } from "react";

import { getUserFacingErrorMessage } from "../../../shared/feedback_details.js";
import {
  applyRangeModeDefaults,
  buildStatsRequestParams,
  createInitialStatsFilters,
  validateStatsFilters,
} from "../../stats/stats_shared.js";


function toErrorMessage(error) {
  return getUserFacingErrorMessage(error);
}


function normalizeCell(cell) {
  return {
    display_text: cell?.display_text ? String(cell.display_text) : "--",
  };
}


function normalizeAccountCapabilityStatsResponse(response) {
  return {
    items: Array.isArray(response?.items)
      ? response.items.map((item) => ({
        account_id: String(item?.account_id ?? ""),
        account_display_name: item?.account_display_name
          ? String(item.account_display_name)
          : "未命名账号",
        new_api: normalizeCell(item?.new_api),
        fast_api: normalizeCell(item?.fast_api),
        browser: normalizeCell(item?.browser),
        create_order: normalizeCell(item?.create_order),
        submit_order: normalizeCell(item?.submit_order),
      })).filter((item) => item.account_id)
      : [],
  };
}


export function useAccountCapabilityStatsPage({ client }) {
  const filtersRef = useRef(null);
  const [filters, setFilters] = useState(() => {
    const initialFilters = createInitialStatsFilters();
    filtersRef.current = initialFilters;
    return initialFilters;
  });
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

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
      setLoadError(validationError);
      return;
    }

    setIsLoading(true);
    try {
      const response = await client.getAccountCapabilityStats(buildStatsRequestParams(nextFilters));
      setRows(normalizeAccountCapabilityStatsResponse(response).items);
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
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
      setLoadError("");
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
