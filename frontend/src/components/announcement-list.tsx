"use client";

import { format, parseISO } from "date-fns";
import type { Filing } from "@/lib/api";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

const CATEGORY_COLORS: Record<string, string> = {
  "Financial Results": "bg-blue-50 text-blue-700",
  "Concall Transcript": "bg-purple-50 text-purple-700",
  "Investor Presentation": "bg-indigo-50 text-indigo-700",
  "Investor/Analyst Meet": "bg-violet-50 text-violet-700",
  "Operational Update": "bg-cyan-50 text-cyan-700",
  "Board Meeting": "bg-emerald-50 text-emerald-700",
  "New Order": "bg-green-50 text-green-700",
  "Mergers/Acquisitions": "bg-rose-50 text-rose-700",
  "Regulatory Approvals/Orders": "bg-amber-50 text-amber-700",
  "Credit Rating": "bg-teal-50 text-teal-700",
  "Clarifications/Confirmations": "bg-orange-50 text-orange-700",
  "Insider Trading": "bg-yellow-50 text-yellow-700",
  "Debt & Financing": "bg-lime-50 text-lime-700",
  "Expansion": "bg-sky-50 text-sky-700",
  "Procedural/Administrative": "bg-gray-50 text-gray-500",
  default: "bg-gray-100 text-gray-600",
};

function getCategoryColor(category: string) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.default;
}

function formatTime(dateStr: string) {
  try {
    const d = parseISO(dateStr);
    return format(d, "d MMM · HH:mm") + " IST";
  } catch {
    return dateStr;
  }
}

interface Props {
  filings: Filing[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (filing: Filing) => void;
  currentPage: number;
  totalPages: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}

export function AnnouncementList({
  filings,
  loading,
  selectedId,
  onSelect,
  currentPage,
  totalPages,
  hasNext,
  onPageChange,
}: Props) {
  if (loading && filings.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-orange-500" />
      </div>
    );
  }

  if (filings.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        No announcements found
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        {filings.map((f, idx) => (
          <button
            key={`${f.corp_id}-${idx}`}
            onClick={() => onSelect(f)}
            className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition ${
              selectedId === f.corp_id ? "bg-orange-50/60" : ""
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-1">
              <span className="text-sm font-semibold text-gray-900 truncate">
                {f.companyname || f.symbol}
              </span>
              <span
                className={`text-[10px] font-medium px-2 py-0.5 rounded whitespace-nowrap uppercase tracking-wide ${getCategoryColor(
                  f.category
                )}`}
              >
                {f.category}
              </span>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2 leading-snug mb-1.5">
              {f.headline || f.summary}
            </p>
            <span className="text-[11px] text-gray-400">
              {formatTime(f.date)}
            </span>
            {f.sentiment && (
              <span
                className={`ml-2 inline-flex items-center text-[10px] font-medium ${
                  f.sentiment === "Positive"
                    ? "text-green-600"
                    : f.sentiment === "Negative"
                    ? "text-red-600"
                    : "text-gray-500"
                }`}
              >
                • {f.sentiment}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Pagination */}
      <div className="border-t border-gray-200 px-4 py-2 flex items-center justify-between bg-white flex-shrink-0">
        <span className="text-xs text-gray-400">
          Page {currentPage} of {totalPages}
        </span>
        <div className="flex items-center gap-1">
          <button
            disabled={currentPage <= 1}
            onClick={() => onPageChange(currentPage - 1)}
            className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} className="text-gray-600" />
          </button>
          <button
            disabled={!hasNext}
            onClick={() => onPageChange(currentPage + 1)}
            className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight size={16} className="text-gray-600" />
          </button>
        </div>
      </div>
    </div>
  );
}
