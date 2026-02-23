"use client";

import { useState, useEffect } from "react";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import {
  format,
  startOfMonth,
  endOfMonth,
  addMonths,
  subMonths,
  eachDayOfInterval,
  getDay,
  isSameDay,
  isToday,
  subDays,
  startOfDay,
  isBefore,
  isAfter,
} from "date-fns";

interface Props {
  open: boolean;
  startDate: Date | null;
  endDate: Date | null;
  onApply: (start: Date | null, end: Date | null) => void;
  onClose: () => void;
}

const PRESETS = [
  { label: "Today", getRange: () => [new Date(), new Date()] as [Date, Date] },
  {
    label: "Yesterday",
    getRange: () => {
      const d = subDays(new Date(), 1);
      return [d, d] as [Date, Date];
    },
  },
  {
    label: "Last 7 Days",
    getRange: () => [subDays(new Date(), 6), new Date()] as [Date, Date],
  },
  {
    label: "Last 30 Days",
    getRange: () => [subDays(new Date(), 29), new Date()] as [Date, Date],
  },
  {
    label: "This Month",
    getRange: () =>
      [startOfMonth(new Date()), new Date()] as [Date, Date],
  },
  {
    label: "Last Month",
    getRange: () => {
      const prev = subMonths(new Date(), 1);
      return [startOfMonth(prev), endOfMonth(prev)] as [Date, Date];
    },
  },
];

export function DateFilterModal({
  open,
  startDate,
  endDate,
  onApply,
  onClose,
}: Props) {
  const [localStart, setLocalStart] = useState<Date | null>(startDate);
  const [localEnd, setLocalEnd] = useState<Date | null>(endDate);
  const [selecting, setSelecting] = useState<"start" | "end">("start");
  const [month1, setMonth1] = useState(subMonths(new Date(), 1));
  const [month2, setMonth2] = useState(new Date());

  useEffect(() => {
    if (open) {
      setLocalStart(startDate);
      setLocalEnd(endDate);
      setSelecting("start");
      setMonth1(subMonths(new Date(), 1));
      setMonth2(new Date());
    }
  }, [open, startDate, endDate]);

  if (!open) return null;

  const handleDayClick = (day: Date) => {
    if (selecting === "start") {
      setLocalStart(day);
      setLocalEnd(null);
      setSelecting("end");
    } else {
      if (localStart && isBefore(day, localStart)) {
        setLocalStart(day);
        setLocalEnd(localStart);
      } else {
        setLocalEnd(day);
      }
      setSelecting("start");
    }
  };

  const handlePreset = (start: Date, end: Date) => {
    setLocalStart(start);
    setLocalEnd(end);
  };

  const handleClear = () => {
    setLocalStart(null);
    setLocalEnd(null);
  };

  const prevMonth = () => {
    setMonth1(subMonths(month1, 1));
    setMonth2(subMonths(month2, 1));
  };

  const nextMonth = () => {
    setMonth1(addMonths(month1, 1));
    setMonth2(addMonths(month2, 1));
  };

  const rangeLabel =
    localStart && localEnd
      ? `${format(localStart, "d MMM yyyy")}  -  ${format(localEnd, "d MMM yyyy")}`
      : localStart
      ? `${format(localStart, "d MMM yyyy")}  -  ...`
      : "Select date range";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh]">
      <div className="fixed inset-0 bg-black/20" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-[720px] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Date</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Current range */}
        <div className="px-6 py-3 flex items-center justify-center gap-3 border-b border-gray-50">
          <span className="text-sm text-gray-700">{rangeLabel}</span>
          {(localStart || localEnd) && (
            <button
              onClick={handleClear}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Clear
            </button>
          )}
        </div>

        {/* Body: presets + calendars */}
        <div className="flex">
          {/* Presets */}
          <div className="w-[160px] border-r border-gray-100 py-4 px-4 space-y-1">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => {
                  const [s, e] = p.getRange();
                  handlePreset(s, e);
                }}
                className="block w-full text-left text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-50 px-3 py-2 rounded-lg transition"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Calendars */}
          <div className="flex-1 py-4 px-6">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={prevMonth}
                className="p-1 hover:bg-gray-100 rounded transition"
              >
                <ChevronLeft size={16} />
              </button>
              <div className="flex gap-16">
                <span className="text-sm font-semibold text-gray-900">
                  {format(month1, "MMMM yyyy")}
                </span>
                <span className="text-sm font-semibold text-gray-900">
                  {format(month2, "MMMM yyyy")}
                </span>
              </div>
              <button
                onClick={nextMonth}
                className="p-1 hover:bg-gray-100 rounded transition"
              >
                <ChevronRight size={16} />
              </button>
            </div>

            <div className="flex gap-8">
              <CalendarGrid
                month={month1}
                start={localStart}
                end={localEnd}
                onDayClick={handleDayClick}
              />
              <CalendarGrid
                month={month2}
                start={localStart}
                end={localEnd}
                onDayClick={handleDayClick}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 font-medium transition"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onApply(localStart, localEnd);
              onClose();
            }}
            className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Calendar Grid ──────────────────────────────────
function CalendarGrid({
  month,
  start,
  end,
  onDayClick,
}: {
  month: Date;
  start: Date | null;
  end: Date | null;
  onDayClick: (d: Date) => void;
}) {
  const days = eachDayOfInterval({
    start: startOfMonth(month),
    end: endOfMonth(month),
  });
  const firstDayOfWeek = getDay(startOfMonth(month));

  return (
    <div className="flex-1">
      {/* Day headers */}
      <div className="grid grid-cols-7 mb-1">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div
            key={d}
            className="text-[11px] font-medium text-gray-400 text-center py-1"
          >
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {/* Blank cells for offset */}
        {Array.from({ length: firstDayOfWeek }).map((_, i) => (
          <div key={`blank-${i}`} />
        ))}
        {days.map((day) => {
          const isStart = start && isSameDay(day, start);
          const isEnd = end && isSameDay(day, end);
          const inRange =
            start && end && isAfter(day, start) && isBefore(day, end);
          const isTodayDate = isToday(day);
          const isFuture = isAfter(startOfDay(day), startOfDay(new Date()));

          return (
            <button
              key={day.toISOString()}
              disabled={isFuture}
              onClick={() => onDayClick(day)}
              className={`w-9 h-9 text-sm rounded-full flex items-center justify-center transition ${
                isStart || isEnd
                  ? "bg-blue-600 text-white font-semibold"
                  : inRange
                  ? "bg-blue-50 text-blue-700"
                  : isTodayDate
                  ? "ring-1 ring-blue-400 text-blue-600 font-medium"
                  : isFuture
                  ? "text-gray-300 cursor-not-allowed"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              {format(day, "d")}
            </button>
          );
        })}
      </div>
    </div>
  );
}
