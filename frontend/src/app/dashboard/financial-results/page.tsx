"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { getFinancialResults } from "@/lib/api";
import type { FinancialResult } from "@/lib/api";
import { BarChart3, RefreshCcw, TrendingUp, TrendingDown, ArrowLeft } from "lucide-react";
import { format, parseISO } from "date-fns";
import { InlineDatePicker } from "@/components/inline-date-picker";

function formatCrores(val: number | null): string {
  if (val === null || val === undefined) return "—";
  if (Math.abs(val) >= 100) return `₹${(val / 100).toFixed(1)} Cr`;
  return `₹${val.toFixed(1)} L`;
}

function YoyBadge({ val }: { val: number | null }) {
  if (val === null || val === undefined) return <span className="text-gray-400 text-xs">—</span>;
  const positive = val >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full ${
        positive ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
      }`}
    >
      {positive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
      {positive ? "+" : ""}
      {val.toFixed(1)}%
    </span>
  );
}

export default function FinancialResultsPage() {
  const { token } = useAuth();
  const [results, setResults] = useState<FinancialResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [selected, setSelected] = useState<FinancialResult | null>(null);

  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [fetchKey, setFetchKey] = useState(0);
  const pageRef = useRef(1);

  // Fetch data when filters change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setSelected(null);
    pageRef.current = 1;
    getFinancialResults({
      start_date: startDate,
      end_date: endDate,
      page: 1,
      page_size: 30,
    }).then((res) => {
      if (cancelled) return;
      setResults(res.financial_results);
      setTotalCount(res.total_count);
      setHasNext(res.has_next);
      setPage(res.current_page);
    }).catch((err) => {
      if (!cancelled) console.error("Failed to fetch financial results:", err);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [startDate, endDate, fetchKey]);

  const handleLoadMore = () => {
    if (!hasNext) return;
    const nextPage = page + 1;
    getFinancialResults({
      start_date: startDate,
      end_date: endDate,
      page: nextPage,
      page_size: 30,
    }).then((res) => {
      setResults((prev) => [...prev, ...res.financial_results]);
      setTotalCount(res.total_count);
      setHasNext(res.has_next);
      setPage(res.current_page);
    }).catch(console.error);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 md:px-6 py-3 md:py-4 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-3 bg-white">
        <div className="flex items-center gap-2">
          {selected && (
            <button
              onClick={() => setSelected(null)}
              className="md:hidden p-1 -ml-1 mr-1 text-gray-500 hover:text-gray-900 transition"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <BarChart3 size={18} className="text-indigo-500" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">Financial Results</h1>
          <span className="text-xs text-gray-400 ml-2">
            {totalCount.toLocaleString()} results
          </span>
        </div>
        <div className="flex items-center gap-3">
          <InlineDatePicker
            startDate={startDate}
            endDate={endDate}
            onChange={(s, e) => { setStartDate(s); setEndDate(e); }}
          />
          <button
            onClick={() => setFetchKey((k) => k + 1)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 transition"
          >
            <RefreshCcw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* List */}
        <div className={`w-full md:w-[480px] md:shrink-0 border-r border-gray-100 overflow-y-auto ${selected ? "hidden md:block" : "block"}`}>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : results.length === 0 ? (
            <div className="py-16 text-center text-sm text-gray-400">
              No financial results found for today
            </div>
          ) : (
            <>
              {results.map((r) => {
                const isActive = selected?.id === r.id;
                const companyName =
                  r.corporatefilings?.companyname || r.company_id;
                return (
                  <button
                    key={r.id}
                    onClick={() => setSelected(r)}
                    className={`w-full text-left px-5 py-4 border-b border-gray-50 transition ${
                      isActive
                        ? "bg-orange-50 border-l-2 border-l-orange-500"
                        : "hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-gray-900 truncate">
                          {companyName}
                        </p>
                        <p className="text-[11px] text-gray-400 mt-0.5">
                          {r.corporatefilings?.symbol} · {r.period}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <YoyBadge val={r.pat_yoy} />
                        <span className="text-[10px] text-gray-400">PAT YoY</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 mt-2">
                      <div className="text-[11px]">
                        <span className="text-gray-400">Sales: </span>
                        <span className="text-gray-700 font-medium">
                          {formatCrores(r.sales_current)}
                        </span>
                      </div>
                      <div className="text-[11px]">
                        <span className="text-gray-400">PAT: </span>
                        <span className="text-gray-700 font-medium">
                          {formatCrores(r.pat_current)}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
              {hasNext && (
                <div className="p-4 text-center">
                  <button
                    onClick={handleLoadMore}
                    className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Load More
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail */}
        <div className={`flex-1 overflow-y-auto ${selected ? "block" : "hidden md:block"}`}>
          {selected ? (
            <div className="p-4 md:p-8">
              <h2 className="text-lg font-bold text-gray-900 mb-1">
                {selected.corporatefilings?.companyname || selected.company_id}
              </h2>
              <p className="text-xs text-gray-400 mb-6">
                {selected.corporatefilings?.symbol} · {selected.period} ·{" "}
                {selected.corporatefilings?.date
                  ? format(parseISO(selected.corporatefilings.date), "d MMM yyyy")
                  : ""}
              </p>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">
                    Sales (Current)
                  </p>
                  <p className="text-lg font-bold text-gray-900">
                    {formatCrores(selected.sales_current)}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] text-gray-400">
                      Prev: {formatCrores(selected.sales_previous_year)}
                    </span>
                    <YoyBadge val={selected.sales_yoy} />
                  </div>
                </div>
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">
                    PAT (Current)
                  </p>
                  <p className="text-lg font-bold text-gray-900">
                    {formatCrores(selected.pat_current)}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] text-gray-400">
                      Prev: {formatCrores(selected.pat_previous)}
                    </span>
                    <YoyBadge val={selected.pat_yoy} />
                  </div>
                </div>
              </div>

              {selected.corporatefilings?.ai_summary && (
                <div className="border-t border-gray-100 pt-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">
                    AI Summary
                  </h3>
                  <p className="text-[13px] text-gray-700 leading-relaxed text-justify">
                    {selected.corporatefilings.ai_summary}
                  </p>
                </div>
              )}

              {selected.fileurl && (
                <div className="mt-6">
                  <a
                    href={selected.fileurl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
                  >
                    View Original Filing
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <BarChart3 size={32} className="mb-3 text-gray-300" />
              <p className="text-sm">Select a result to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
