import { useEffect, useRef, useState } from "react";

import {
  StatsDayPickerPanel,
  StatsRangePickerPanel,
} from "./stats_calendar_panel.jsx";
import {
  createTodayDateString,
  formatStatsDayDisplay,
  formatStatsRangeDisplay,
} from "./stats_shared.js";


function formatDateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


function parseDateString(value) {
  const candidate = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(candidate)) {
    return new Date();
  }
  const [year, month, day] = candidate.split("-").map(Number);
  return new Date(year, month - 1, day);
}


function addDaysToDateString(dateString, delta) {
  const nextDate = parseDateString(dateString);
  nextDate.setDate(nextDate.getDate() + delta);
  return formatDateString(nextDate);
}


function getMonthStartDateString(dateString) {
  const currentDate = parseDateString(dateString);
  return formatDateString(new Date(currentDate.getFullYear(), currentDate.getMonth(), 1));
}


function getDisplayLabel(rangeMode) {
  if (rangeMode === "range") {
    return "统计时间段";
  }
  if (rangeMode === "day") {
    return "统计日期";
  }
  return "统计范围";
}


function getDisplayValue(filters) {
  if (filters.rangeMode === "range") {
    return formatStatsRangeDisplay(filters.startDate, filters.endDate);
  }
  if (filters.rangeMode === "day") {
    return formatStatsDayDisplay(filters.date);
  }
  return "累计全量统计";
}


export function StatsRangeControls({
  filters,
  onDateChange,
  onEndDateChange,
  onRangeModeChange,
  onRefresh,
  onStartDateChange,
}) {
  const containerRef = useRef(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const keepPickerOpenOnModeChangeRef = useRef(false);
  const pickerMode = filters.rangeMode === "range" ? "range" : "day";

  useEffect(() => {
    if (keepPickerOpenOnModeChangeRef.current) {
      keepPickerOpenOnModeChangeRef.current = false;
      setIsPickerOpen(true);
      return;
    }

    setIsPickerOpen(false);
  }, [filters.rangeMode]);

  useEffect(() => {
    if (!isPickerOpen) {
      return undefined;
    }

    function handleDocumentMouseDown(event) {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (containerRef.current?.contains(target)) {
        return;
      }

      keepPickerOpenOnModeChangeRef.current = false;
      setIsPickerOpen(false);
    }

    document.addEventListener("mousedown", handleDocumentMouseDown);
    return () => {
      document.removeEventListener("mousedown", handleDocumentMouseDown);
    };
  }, [isPickerOpen]);

  function handleQuickTotal() {
    keepPickerOpenOnModeChangeRef.current = false;
    setIsPickerOpen(false);
    onRangeModeChange("total");
  }

  function handleQuickToday() {
    const today = createTodayDateString();
    keepPickerOpenOnModeChangeRef.current = true;
    onDateChange(today);
    onRangeModeChange("day");
  }

  function handleQuickRecentSevenDays() {
    const today = createTodayDateString();
    keepPickerOpenOnModeChangeRef.current = true;
    onStartDateChange(addDaysToDateString(today, -6));
    onEndDateChange(today);
    onRangeModeChange("range");
  }

  function handleQuickCurrentMonth() {
    const today = createTodayDateString();
    keepPickerOpenOnModeChangeRef.current = true;
    onStartDateChange(getMonthStartDateString(today));
    onEndDateChange(today);
    onRangeModeChange("range");
  }

  return (
    <>
      <div ref={containerRef} className="stats-range-display">
        <button
          aria-expanded={isPickerOpen}
          aria-label="打开统计时间选择"
          className={`stats-range-display__button${isPickerOpen ? " is-open" : ""}`}
          type="button"
          onClick={() => setIsPickerOpen((current) => !current)}
        >
          <span className="stats-range-display__label">{getDisplayLabel(filters.rangeMode)}</span>
          <span className="stats-range-display__value">{getDisplayValue(filters)}</span>
        </button>

        {isPickerOpen ? (
          <div className="stats-range-display__popover">
            {pickerMode === "range" ? (
              <StatsRangePickerPanel
                endDate={filters.endDate}
                onEndDateChange={onEndDateChange}
                onQuickCurrentMonth={handleQuickCurrentMonth}
                onQuickRecentSevenDays={handleQuickRecentSevenDays}
                onQuickSelectToday={handleQuickToday}
                onQuickSelectTotal={handleQuickTotal}
                onStartDateChange={onStartDateChange}
                startDate={filters.startDate}
              />
            ) : (
              <StatsDayPickerPanel
                date={filters.date}
                onDateChange={(nextValue) => {
                  onDateChange(nextValue);
                  if (filters.rangeMode !== "day") {
                    onRangeModeChange("day");
                  }
                }}
                onQuickCurrentMonth={handleQuickCurrentMonth}
                onQuickRecentSevenDays={handleQuickRecentSevenDays}
                onQuickSelectToday={handleQuickToday}
                onQuickSelectTotal={handleQuickTotal}
              />
            )}
          </div>
        ) : null}
      </div>

      <button className="ghost-button stats-toolbar__refresh" type="button" onClick={onRefresh}>
        刷新统计
      </button>
    </>
  );
}
