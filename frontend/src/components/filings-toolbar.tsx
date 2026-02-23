"use client";

import { useState } from "react";
import { format } from "date-fns";
import type { FilingsParams } from "@/lib/api";

interface Props {
  totalCount: number;
  showUnread: boolean;
  onToggleUnread: () => void;
  onFilterChange: (filters: FilingsParams) => void;
  filters: FilingsParams;
}

export function FilingsToolbar({
  totalCount,
  showUnread,
  onToggleUnread,
  onFilterChange,
  filters,
}: Props) {
  const [sortBy, setSortBy] = useState("Latest");
  const today = format(new Date(), "d MMM");

  const hasActiveFilters =
    filters.category || filters.symbol || filters.start_date;

  return (
    <div className="border-b border-gray-200 bg-white">
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-gray-900">
            Announcements
          </h2>
          <span className="text-sm text-gray-400">({totalCount})</span>
        </div>
        <div className="flex items-center gap-1">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="text-xs text-gray-500 bg-transparent border border-gray-200 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-300"
          >
            <option value="Latest">Sort by: Latest</option>
            <option value="Oldest">Sort by: Oldest</option>
          </select>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-4 flex items-center gap-2 pb-2">
        <button
          onClick={() => showUnread && onToggleUnread()}
          className={`px-3 py-1 text-xs font-medium rounded-md transition ${
            !showUnread
              ? "bg-gray-900 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          All
        </button>
        <button
          onClick={() => !showUnread && onToggleUnread()}
          className={`px-3 py-1 text-xs font-medium rounded-md transition ${
            showUnread
              ? "bg-gray-900 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          Unread
        </button>

        {hasActiveFilters && (
          <button
            onClick={() => onFilterChange({})}
            className="ml-auto text-xs text-orange-500 hover:text-orange-600 font-medium"
          >
            Reset All
          </button>
        )}
      </div>

      {/* Date filter row */}
      <div className="px-4 py-2 border-t border-gray-100 flex items-center gap-4 text-xs">
        <label className="flex items-center gap-1.5 text-gray-500">
          <span className="font-medium text-gray-700 uppercase tracking-wide">
            Date
          </span>
          <input
            type="date"
            value={filters.start_date || ""}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                start_date: e.target.value || undefined,
                end_date: e.target.value || undefined,
              })
            }
            className="border border-gray-200 rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-orange-300"
          />
        </label>

        <label className="flex items-center gap-1.5 text-gray-500">
          <span className="font-medium text-gray-700 uppercase tracking-wide">
            Category
          </span>
          <select
            value={filters.category || ""}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                category: e.target.value || undefined,
              })
            }
            className="border border-gray-200 rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-orange-300 max-w-[140px]"
          >
            <option value="">All</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-1.5 text-gray-500">
          <span className="font-medium text-gray-700 uppercase tracking-wide">
            Company
          </span>
          <input
            type="text"
            placeholder="Symbol..."
            value={filters.symbol || ""}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                symbol: e.target.value || undefined,
              })
            }
            className="border border-gray-200 rounded-md px-2 py-1 text-xs w-[90px] focus:outline-none focus:ring-1 focus:ring-orange-300"
          />
        </label>
      </div>
    </div>
  );
}

const CATEGORIES = [
  "Financial Results",
  "Concall Transcript",
  "Investor Presentation",
  "Investor/Analyst Meet",
  "Operational Update",
  "Board Meeting",
  "New Order",
  "Mergers/Acquisitions",
  "Regulatory Approvals/Orders",
  "Credit Rating",
  "Change in KMP",
  "Debt & Financing",
  "Expansion",
  "Divestitures",
  "Joint Ventures",
  "Fundraise - Preferential Issue",
  "Fundraise - QIP",
  "Fundraise - Rights Issue",
  "Bonus/Stock Split",
  "Buyback",
  "Open Offer",
  "Insider Trading",
  "Litigation & Notices",
  "Clarifications/Confirmations",
  "Agreements/MoUs",
  "Incorporation/Cessation of Subsidiary",
  "Increase in Share Capital",
  "Insolvency and Bankruptcy",
  "Name Change",
  "New Product",
  "USFDA",
  "Demerger",
  "Delisting",
  "Procedural/Administrative",
];
