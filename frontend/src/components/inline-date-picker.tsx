"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { format, subDays, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, isToday, addMonths, subMonths, startOfWeek, endOfWeek } from "date-fns";

interface Props {
  startDate: string;
  endDate: string;
  onChange: (start: string, end: string) => void;
}

const presets = [
  { label: "Today", days: 0 },
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
];

export function InlineDatePicker({ startDate, endDate, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(new Date());
  const dropRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [dropPos, setDropPos] = useState({ top: 0, left: 0 });

  // Compute dropdown position when opening
  useEffect(() => {
    if (open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setDropPos({ top: r.bottom + 4, left: Math.max(8, r.right - 280) });
    }
  }, [open]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (
        dropRef.current && !dropRef.current.contains(target) &&
        btnRef.current && !btnRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handlePreset = (days: number) => {
    const today = new Date();
    const start = days === 0 ? today : subDays(today, days);
    onChange(format(start, "yyyy-MM-dd"), format(today, "yyyy-MM-dd"));
    setOpen(false);
  };

  const handleDayClick = (day: Date) => {
    const dayStr = format(day, "yyyy-MM-dd");
    // If no start selected or both selected, start fresh
    if (!startDate || (startDate && endDate && startDate !== endDate)) {
      onChange(dayStr, dayStr);
    } else {
      // Set end date
      if (dayStr < startDate) {
        onChange(dayStr, startDate);
      } else {
        onChange(startDate, dayStr);
      }
      setOpen(false);
    }
  };

  const displayLabel = startDate === endDate
    ? (isToday(new Date(startDate + "T00:00:00")) ? "Today" : format(new Date(startDate + "T00:00:00"), "d MMM yyyy"))
    : `${format(new Date(startDate + "T00:00:00"), "d MMM")} – ${format(new Date(endDate + "T00:00:00"), "d MMM yyyy")}`;

  const monthStart = startOfMonth(viewMonth);
  const monthEnd = endOfMonth(viewMonth);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const calDays = eachDayOfInterval({ start: calStart, end: calEnd });

  return (
    <div>
      <button
        ref={btnRef}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition text-gray-700"
      >
        <CalendarDays size={14} className="text-gray-400" />
        {displayLabel}
      </button>
      {open && createPortal(
        <div
          ref={dropRef}
          className="fixed z-[9999] bg-white border border-gray-200 rounded-xl shadow-xl p-3 w-[280px]"
          style={{ top: dropPos.top, left: dropPos.left }}
        >
          {/* Presets */}
          <div className="flex gap-1 mb-3">
            {presets.map((p) => {
              const today = new Date();
              const pStart = p.days === 0 ? format(today, "yyyy-MM-dd") : format(subDays(today, p.days), "yyyy-MM-dd");
              const pEnd = format(today, "yyyy-MM-dd");
              const active = startDate === pStart && endDate === pEnd;
              return (
                <button
                  key={p.label}
                  onClick={() => handlePreset(p.days)}
                  className={`flex-1 text-[11px] font-medium py-1.5 rounded-lg transition ${
                    active
                      ? "bg-gray-900 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {/* Month nav */}
          <div className="flex items-center justify-between mb-2">
            <button onClick={() => setViewMonth(subMonths(viewMonth, 1))} className="p-1 hover:bg-gray-100 rounded">
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs font-semibold text-gray-700">
              {format(viewMonth, "MMMM yyyy")}
            </span>
            <button onClick={() => setViewMonth(addMonths(viewMonth, 1))} className="p-1 hover:bg-gray-100 rounded">
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 gap-0 mb-1">
            {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => (
              <div key={d} className="text-center text-[10px] font-medium text-gray-400 py-1">
                {d}
              </div>
            ))}
          </div>

          {/* Days */}
          <div className="grid grid-cols-7 gap-0">
            {calDays.map((day) => {
              const dayStr = format(day, "yyyy-MM-dd");
              const inMonth = day.getMonth() === viewMonth.getMonth();
              const isStart = dayStr === startDate;
              const isEnd = dayStr === endDate;
              const inRange = dayStr >= startDate && dayStr <= endDate;
              const isEdge = isStart || isEnd;

              return (
                <button
                  key={dayStr}
                  onClick={() => handleDayClick(day)}
                  className={`h-8 text-[11px] rounded-md transition ${
                    !inMonth
                      ? "text-gray-300"
                      : isEdge
                      ? "bg-gray-900 text-white font-bold"
                      : inRange
                      ? "bg-gray-100 text-gray-900 font-medium"
                      : isToday(day)
                      ? "text-orange-600 font-semibold hover:bg-orange-50"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {format(day, "d")}
                </button>
              );
            })}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
