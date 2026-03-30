const MODE_LABELS = {
  new_api: "api查询器",
  fast_api: "api高速查询器",
  token: "浏览器查询器",
  browser: "浏览器查询器",
};


function formatDateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


export function createTodayDateString() {
  return formatDateString(new Date());
}


function normalizeDateString(value) {
  const candidate = String(value || "").trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(candidate) ? candidate : createTodayDateString();
}


export function createInitialStatsFilters() {
  const today = createTodayDateString();
  return {
    rangeMode: "day",
    date: today,
    startDate: today,
    endDate: today,
  };
}


export function applyRangeModeDefaults(currentFilters, nextRangeMode) {
  const today = createTodayDateString();
  const fallbackDate = currentFilters.date || currentFilters.endDate || today;
  if (nextRangeMode === "day") {
    return {
      ...currentFilters,
      rangeMode: "day",
      date: currentFilters.date || fallbackDate,
    };
  }
  if (nextRangeMode === "range") {
    return {
      ...currentFilters,
      rangeMode: "range",
      startDate: currentFilters.startDate || currentFilters.date || fallbackDate,
      endDate: currentFilters.endDate || currentFilters.date || fallbackDate,
    };
  }
  return {
    ...currentFilters,
    rangeMode: "total",
  };
}


export function buildStatsRequestParams(filters) {
  if (filters.rangeMode === "day") {
    return {
      rangeMode: "day",
      date: filters.date,
    };
  }
  if (filters.rangeMode === "range") {
    return {
      rangeMode: "range",
      startDate: filters.startDate,
      endDate: filters.endDate,
    };
  }
  return {
    rangeMode: "total",
  };
}


export function validateStatsFilters(filters) {
  if (filters.rangeMode === "day" && !filters.date) {
    return "请选择统计日期";
  }
  if (filters.rangeMode === "range" && (!filters.startDate || !filters.endDate)) {
    return "请选择开始和结束日期";
  }
  return "";
}


export function formatModeLabel(modeType) {
  return MODE_LABELS[modeType] || String(modeType || "--");
}


export function formatStatsDayDisplay(date) {
  return `${normalizeDateString(date)} 00:00:00`;
}


export function formatStatsRangeDisplay(startDate, endDate) {
  return `${normalizeDateString(startDate)} 00:00:00 ~ ${normalizeDateString(endDate)} 23:59:59`;
}


export function formatQuerySourceModeSummary(sourceModeStats) {
  if (!Array.isArray(sourceModeStats) || sourceModeStats.length === 0) {
    return "--";
  }

  return sourceModeStats
    .map((entry) => `${formatModeLabel(entry?.mode_type)} ${Number(entry?.hit_count ?? 0)}`)
    .join(" · ");
}
