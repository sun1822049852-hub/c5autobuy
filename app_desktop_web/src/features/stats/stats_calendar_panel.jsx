import { useEffect, useMemo, useState } from "react";

import {
  formatStatsDayDisplay,
} from "./stats_shared.js";


const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"];


function createTodayDateString() {
  return new Date().toISOString().slice(0, 10);
}


function normalizeDateString(value) {
  const candidate = String(value || "").trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(candidate) ? candidate : createTodayDateString();
}


function parseDateString(value) {
  const normalized = normalizeDateString(value);
  const [year, month, day] = normalized.split("-").map(Number);
  return new Date(year, month - 1, day);
}


function formatDateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


function formatSlashDate(dateString) {
  return normalizeDateString(dateString).replaceAll("-", "/");
}


function formatMonthHeading(date) {
  return `${date.getFullYear()}年${date.getMonth() + 1}月`;
}


function addMonths(date, delta) {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}


function addDays(date, delta) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + delta);
  return nextDate;
}


function compareDateStrings(left, right) {
  return normalizeDateString(left).localeCompare(normalizeDateString(right));
}


function buildMonthCells(anchorDate) {
  const monthStart = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1);
  const calendarStart = addDays(monthStart, -monthStart.getDay());
  const weeks = [];

  for (let weekIndex = 0; weekIndex < 6; weekIndex += 1) {
    const week = [];
    for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
      const currentDate = addDays(calendarStart, weekIndex * 7 + dayIndex);
      week.push({
        dateString: formatDateString(currentDate),
        dayNumber: currentDate.getDate(),
        isCurrentMonth: currentDate.getMonth() === anchorDate.getMonth(),
      });
    }
    weeks.push(week);
  }

  return {
    heading: formatMonthHeading(anchorDate),
    weeks,
  };
}


function isDateWithinRange(dateString, startDate, endDate) {
  return compareDateStrings(dateString, startDate) >= 0 && compareDateStrings(dateString, endDate) <= 0;
}


function CalendarMonth({
  endDate,
  maxDate,
  mode,
  monthDate,
  onSelectDate,
  selectedDate,
  startDate,
}) {
  const monthModel = useMemo(() => buildMonthCells(monthDate), [monthDate]);

  return (
    <section className="stats-calendar__month">
      <header className="stats-calendar__month-header">
        <div className="stats-calendar__month-title">{monthModel.heading}</div>
      </header>

      <div className="stats-calendar__weekday-row">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="stats-calendar__weekday">{label}</div>
        ))}
      </div>

      <div className="stats-calendar__week-grid">
        {monthModel.weeks.flat().map((cell) => {
          const isDisabled = maxDate
            ? compareDateStrings(cell.dateString, maxDate) > 0
            : false;
          const dayAriaLabel = cell.isCurrentMonth
            ? `选择日期 ${cell.dateString}`
            : `相邻月份日期 ${cell.dateString}`;
          const isSelected = mode === "day"
            ? compareDateStrings(cell.dateString, selectedDate) === 0
            : compareDateStrings(cell.dateString, startDate) === 0
              || compareDateStrings(cell.dateString, endDate) === 0;
          const isInRange = mode === "range" && isDateWithinRange(cell.dateString, startDate, endDate);

          return (
            <button
              key={cell.dateString}
              aria-label={dayAriaLabel}
              className={`stats-calendar__day${cell.isCurrentMonth ? "" : " is-muted"}${isSelected ? " is-selected" : ""}${isInRange ? " is-in-range" : ""}${isDisabled ? " is-disabled" : ""}`.trim()}
              disabled={isDisabled}
              type="button"
              onClick={() => onSelectDate(cell.dateString)}
            >
              {cell.dayNumber}
            </button>
          );
        })}
      </div>
    </section>
  );
}


function StatsCalendarQuickActions({
  onCurrentMonth,
  onRecentSevenDays,
  onSelectToday,
  onSelectTotal,
}) {
  return (
    <div className="stats-calendar__quick-actions" role="group" aria-label="快捷统计范围">
      <button className="stats-calendar__quick-action" type="button" onClick={onSelectTotal}>
        总计
      </button>
      <button className="stats-calendar__quick-action" type="button" onClick={onSelectToday}>
        今天
      </button>
      <button className="stats-calendar__quick-action" type="button" onClick={onRecentSevenDays}>
        近7天
      </button>
      <button className="stats-calendar__quick-action" type="button" onClick={onCurrentMonth}>
        本月
      </button>
    </div>
  );
}


export function StatsDayPickerPanel({
  date,
  onDateChange,
  onQuickCurrentMonth,
  onQuickRecentSevenDays,
  onQuickSelectToday,
  onQuickSelectTotal,
}) {
  const [visibleMonth, setVisibleMonth] = useState(() => parseDateString(date));
  const maxDate = createTodayDateString();

  useEffect(() => {
    setVisibleMonth(parseDateString(date));
  }, [date]);

  return (
    <div aria-label="选择统计日期" className="stats-calendar stats-calendar--wide" role="dialog">
      <div className="stats-calendar__selection-bar">
        <div className="stats-calendar__selection-chip is-active">
          <span className="stats-calendar__selection-label">统计日期</span>
          <span className="stats-calendar__selection-value">{formatStatsDayDisplay(date)}</span>
        </div>
      </div>

      <div className="stats-calendar__nav-row">
        <button
          aria-label="上一月"
          className="stats-calendar__nav-button"
          type="button"
          onClick={() => setVisibleMonth((current) => addMonths(current, -1))}
        >
          {"<"}
        </button>
        <div className="stats-calendar__nav-spacer" />
        <button
          aria-label="下一月"
          className="stats-calendar__nav-button"
          type="button"
          onClick={() => setVisibleMonth((current) => addMonths(current, 1))}
        >
          {">"}
        </button>
      </div>

      <div className="stats-calendar__range-grid">
        <CalendarMonth
          maxDate={maxDate}
          mode="day"
          monthDate={visibleMonth}
          onSelectDate={onDateChange}
          selectedDate={date}
        />

        <CalendarMonth
          maxDate={maxDate}
          mode="day"
          monthDate={addMonths(visibleMonth, 1)}
          onSelectDate={onDateChange}
          selectedDate={date}
        />
      </div>

      <div className="stats-calendar__footer">
        <div className="stats-calendar__footer-value">{formatSlashDate(date)} 00:00:00</div>
      </div>

      <StatsCalendarQuickActions
        onCurrentMonth={onQuickCurrentMonth}
        onRecentSevenDays={onQuickRecentSevenDays}
        onSelectToday={onQuickSelectToday}
        onSelectTotal={onQuickSelectTotal}
      />
    </div>
  );
}


export function StatsRangePickerPanel({
  endDate,
  onEndDateChange,
  onQuickCurrentMonth,
  onQuickRecentSevenDays,
  onQuickSelectToday,
  onQuickSelectTotal,
  onStartDateChange,
  startDate,
}) {
  const [activeEdge, setActiveEdge] = useState("start");
  const [visibleMonth, setVisibleMonth] = useState(() => parseDateString(startDate));
  const maxDate = createTodayDateString();

  useEffect(() => {
    setVisibleMonth(parseDateString(startDate));
  }, [startDate]);

  function applyRangeDate(nextDate) {
    if (activeEdge === "start") {
      if (compareDateStrings(nextDate, endDate) > 0) {
        onStartDateChange(endDate);
        onEndDateChange(nextDate);
      } else {
        onStartDateChange(nextDate);
      }
      setActiveEdge("end");
      return;
    }

    if (compareDateStrings(nextDate, startDate) < 0) {
      onStartDateChange(nextDate);
      onEndDateChange(startDate);
    } else {
      onEndDateChange(nextDate);
    }
  }

  return (
    <div aria-label="选择统计时间段" className="stats-calendar stats-calendar--range" role="dialog">
      <div className="stats-calendar__selection-bar stats-calendar__selection-bar--range">
        <button
          aria-label={`开始日期 ${formatStatsDayDisplay(startDate)}`}
          className={`stats-calendar__selection-chip${activeEdge === "start" ? " is-active" : ""}`}
          type="button"
          onClick={() => setActiveEdge("start")}
        >
          <span className="stats-calendar__selection-label">开始日期</span>
          <span className="stats-calendar__selection-value">{formatStatsDayDisplay(startDate)}</span>
        </button>

        <button
          aria-label={`结束日期 ${normalizeDateString(endDate)} 23:59:59`}
          className={`stats-calendar__selection-chip${activeEdge === "end" ? " is-active" : ""}`}
          type="button"
          onClick={() => setActiveEdge("end")}
        >
          <span className="stats-calendar__selection-label">结束日期</span>
          <span className="stats-calendar__selection-value">{normalizeDateString(endDate)} 23:59:59</span>
        </button>
      </div>

      <div className="stats-calendar__nav-row">
        <button
          aria-label="上一月"
          className="stats-calendar__nav-button"
          type="button"
          onClick={() => setVisibleMonth((current) => addMonths(current, -1))}
        >
          {"<"}
        </button>
        <div className="stats-calendar__nav-spacer" />
        <button
          aria-label="下一月"
          className="stats-calendar__nav-button"
          type="button"
          onClick={() => setVisibleMonth((current) => addMonths(current, 1))}
        >
          {">"}
        </button>
      </div>

      <div className="stats-calendar__range-grid">
        <CalendarMonth
          endDate={endDate}
          maxDate={maxDate}
          mode="range"
          monthDate={visibleMonth}
          onSelectDate={applyRangeDate}
          startDate={startDate}
        />

        <CalendarMonth
          endDate={endDate}
          maxDate={maxDate}
          mode="range"
          monthDate={addMonths(visibleMonth, 1)}
          onSelectDate={applyRangeDate}
          startDate={startDate}
        />
      </div>

      <div className="stats-calendar__footer stats-calendar__footer--range">
        <div className="stats-calendar__footer-value">{formatSlashDate(startDate)} 00:00:00</div>
        <div className="stats-calendar__footer-value">{formatSlashDate(endDate)} 23:59:59</div>
      </div>

      <StatsCalendarQuickActions
        onCurrentMonth={onQuickCurrentMonth}
        onRecentSevenDays={onQuickRecentSevenDays}
        onSelectToday={onQuickSelectToday}
        onSelectTotal={onQuickSelectTotal}
      />
    </div>
  );
}
