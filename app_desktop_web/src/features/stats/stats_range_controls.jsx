import { useEffect, useRef, useState } from "react";

import {
  StatsDayPickerPanel,
  StatsRangePickerPanel,
} from "./stats_calendar_panel.jsx";
import {
  formatStatsDayDisplay,
  formatStatsRangeDisplay,
} from "./stats_shared.js";


const RANGE_OPTIONS = [
  { value: "total", label: "总计" },
  { value: "day", label: "按天" },
  { value: "range", label: "时间段" },
];


function createTodayDateString() {
  return new Date().toISOString().slice(0, 10);
}


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


export function StatsRangeControls({
  filters,
  onDateChange,
  onEndDateChange,
  onRangeModeChange,
  onRefresh,
  onStartDateChange,
}) {
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const keepPickerOpenOnModeChangeRef = useRef(false);

  useEffect(() => {
    if (filters.rangeMode === "total") {
      keepPickerOpenOnModeChangeRef.current = false;
      setIsPickerOpen(false);
      return;
    }

    if (keepPickerOpenOnModeChangeRef.current) {
      keepPickerOpenOnModeChangeRef.current = false;
      setIsPickerOpen(true);
      return;
    }

    setIsPickerOpen(false);
  }, [filters.rangeMode]);

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

  function handleRangeModeButtonClick(nextRangeMode) {
    keepPickerOpenOnModeChangeRef.current = false;
    onRangeModeChange(nextRangeMode);
  }

  return (
    <>
      <div aria-label="统计范围" className="stats-range-controls" role="group">
        {RANGE_OPTIONS.map((option) => (
          <button
            key={option.value}
            aria-pressed={filters.rangeMode === option.value}
            className={`stats-range-controls__option${filters.rangeMode === option.value ? " is-active" : ""}`}
            type="button"
            onClick={() => handleRangeModeButtonClick(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {filters.rangeMode === "day" ? (
        <div className="stats-range-display">
          <button
            aria-expanded={isPickerOpen}
            aria-label="打开统计日期选择"
            className={`stats-range-display__button${isPickerOpen ? " is-open" : ""}`}
            type="button"
            onClick={() => setIsPickerOpen((current) => !current)}
          >
            <span className="stats-range-display__label">统计日期</span>
            <span className="stats-range-display__value">{formatStatsDayDisplay(filters.date)}</span>
          </button>

          {isPickerOpen ? (
            <div className="stats-range-display__popover">
              <StatsDayPickerPanel
                date={filters.date}
                onDateChange={onDateChange}
                onQuickCurrentMonth={handleQuickCurrentMonth}
                onQuickRecentSevenDays={handleQuickRecentSevenDays}
                onQuickSelectToday={handleQuickToday}
                onQuickSelectTotal={handleQuickTotal}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {filters.rangeMode === "range" ? (
        <div className="stats-range-display">
          <button
            aria-expanded={isPickerOpen}
            aria-label="打开统计时间段选择"
            className={`stats-range-display__button${isPickerOpen ? " is-open" : ""}`}
            type="button"
            onClick={() => setIsPickerOpen((current) => !current)}
          >
            <span className="stats-range-display__label">统计时间段</span>
            <span className="stats-range-display__value">
              {formatStatsRangeDisplay(filters.startDate, filters.endDate)}
            </span>
          </button>

          {isPickerOpen ? (
            <div className="stats-range-display__popover">
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
            </div>
          ) : null}
        </div>
      ) : null}

      {filters.rangeMode === "total" ? (
        <div className="stats-range-display stats-range-display--summary">
          <div className="stats-range-display__summary-label">统计范围</div>
          <div className="stats-range-display__summary-value">累计全量统计</div>
        </div>
      ) : null}

      <button className="ghost-button stats-toolbar__refresh" type="button" onClick={onRefresh}>
        刷新统计
      </button>
    </>
  );
}
