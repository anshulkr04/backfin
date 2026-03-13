"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { getCorporateActions } from "@/lib/api";
import type { CorporateAction } from "@/lib/api";
import { GitPullRequest, RefreshCcw } from "lucide-react";
import { format, parseISO } from "date-fns";
import { InlineDatePicker } from "@/components/inline-date-picker";

export default function CorporateActionsPage() {
  const { token } = useAuth();
  const [actions, setActions] = useState<CorporateAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [exchange, setExchange] = useState<string>("");

  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [fetchKey, setFetchKey] = useState(0);

  // Fetch data when filters change
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    getCorporateActions(token, {
      start_date: startDate,
      end_date: endDate,
      exchange: exchange || undefined,
      page: 1,
      page_size: 50,
    }).then((res) => {
      if (cancelled) return;
      setActions(res.data);
      setTotalCount(res.pagination.total_records);
      setHasNext(res.pagination.has_next);
      setPage(res.pagination.current_page);
    }).catch((err) => {
      if (!cancelled) console.error("Failed to fetch corporate actions:", err);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [token, startDate, endDate, exchange, fetchKey]);

  const handleLoadMore = () => {
    if (!hasNext || !token) return;
    getCorporateActions(token, {
      start_date: startDate,
      end_date: endDate,
      exchange: exchange || undefined,
      page: page + 1,
      page_size: 50,
    }).then((res) => {
      setActions((prev) => [...prev, ...res.data]);
      setTotalCount(res.pagination.total_records);
      setHasNext(res.pagination.has_next);
      setPage(res.pagination.current_page);
    }).catch(console.error);
  };

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    try {
      return format(parseISO(d), "d MMM yyyy");
    } catch {
      return d;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 md:px-6 py-3 md:py-4 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-3 bg-white">
        <div className="flex items-center gap-2">
          <GitPullRequest size={18} className="text-teal-500" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">
            Corporate Actions
          </h1>
          <span className="text-xs text-gray-400 ml-2">
            {totalCount.toLocaleString()} actions
          </span>
        </div>
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
            {["", "NSE", "BSE"].map((ex) => (
              <button
                key={ex}
                onClick={() => setExchange(ex)}
                className={`px-3 py-1.5 text-xs font-medium transition ${
                  exchange === ex
                    ? "bg-gray-900 text-white"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {ex || "All"}
              </button>
            ))}
          </div>
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

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : actions.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-400">
            No corporate actions found for today
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-[13px] min-w-[700px]">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="text-left px-5 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Symbol
                </th>
                <th className="text-left px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Purpose
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Ex-Date
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Record Date
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Payment Date
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Exchange
                </th>
                <th className="text-center px-5 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {actions.map((action) => (
                <tr
                  key={action.id}
                  className="hover:bg-gray-50 transition"
                >
                  <td className="px-5 py-3">
                    <p className="font-semibold text-gray-900">{action.symbol}</p>
                    <p className="text-[11px] text-gray-400 truncate max-w-[180px]">{action.company_name}</p>
                  </td>
                  <td className="px-3 py-3 text-gray-600 max-w-[300px]">
                    <p className="line-clamp-2 leading-snug">{action.purpose}</p>
                  </td>
                  <td className="px-3 py-3 text-center text-gray-700 font-medium whitespace-nowrap">
                    {formatDate(action.ex_date)}
                  </td>
                  <td className="px-3 py-3 text-center text-gray-500 whitespace-nowrap">
                    {formatDate(action.record_date)}
                  </td>
                  <td className="px-3 py-3 text-center text-gray-500 whitespace-nowrap">
                    {formatDate(action.payment_date)}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className="text-[11px] font-medium text-gray-500">
                      {action.exchange}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-center">
                    {action.action_required ? (
                      <span className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 whitespace-nowrap">
                        Adj. Required
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                        Standard
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
        {hasNext && !loading && (
          <div className="p-4 text-center border-t border-gray-50">
            <button
              onClick={handleLoadMore}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Load More
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
