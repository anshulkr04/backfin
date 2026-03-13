"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { getInsiderTrading } from "@/lib/api";
import type { InsiderTrade } from "@/lib/api";
import {
  UserCheck,
  RefreshCcw,
  ArrowUpRight,
  ArrowDownRight,
  ArrowLeft,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { InlineDatePicker } from "@/components/inline-date-picker";

function formatValue(val: number | null): string {
  if (val === null || val === undefined) return "—";
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(2)} L`;
  return `₹${val.toLocaleString()}`;
}

export default function InsiderTradesPage() {
  const { token } = useAuth();
  const [trades, setTrades] = useState<InsiderTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [exchange, setExchange] = useState<string>("");
  const [selected, setSelected] = useState<InsiderTrade | null>(null);

  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [fetchKey, setFetchKey] = useState(0);

  // Fetch data when filters change
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setSelected(null);
    getInsiderTrading(token, {
      start_date: startDate,
      end_date: endDate,
      exchange: exchange || undefined,
      page: 1,
      page_size: 50,
    }).then((res) => {
      if (cancelled) return;
      setTrades(res.data);
      setTotalCount(res.pagination.total_count);
      setHasNext(res.pagination.has_next);
      setPage(res.pagination.page);
    }).catch((err) => {
      if (!cancelled) console.error("Failed to fetch insider trades:", err);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [token, startDate, endDate, exchange, fetchKey]);

  const handleLoadMore = () => {
    if (!hasNext || !token) return;
    getInsiderTrading(token, {
      start_date: startDate,
      end_date: endDate,
      exchange: exchange || undefined,
      page: page + 1,
      page_size: 50,
    }).then((res) => {
      setTrades((prev) => [...prev, ...res.data]);
      setTotalCount(res.pagination.total_count);
      setHasNext(res.pagination.has_next);
      setPage(res.pagination.page);
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
          <UserCheck size={18} className="text-purple-500" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">Insider Trades</h1>
          <span className="text-xs text-gray-400 ml-2">
            {totalCount.toLocaleString()} trades
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

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* List */}
        <div className={`w-full md:w-[440px] md:shrink-0 border-r border-gray-100 overflow-y-auto ${selected ? "hidden md:block" : "block"}`}>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : trades.length === 0 ? (
            <div className="py-16 text-center text-sm text-gray-400">
              No insider trades found for today
            </div>
          ) : (
            <>
              {trades.map((trade) => {
                const isActive =
                  selected?.insider_uuid === trade.insider_uuid;
                const isAcquisition =
                  trade.trans_type?.toLowerCase().includes("acquisition") ||
                  trade.trans_type?.toLowerCase().includes("buy");
                return (
                  <button
                    key={trade.insider_uuid}
                    onClick={() => setSelected(trade)}
                    className={`w-full text-left px-5 py-4 border-b border-gray-50 transition ${
                      isActive
                        ? "bg-purple-50 border-l-2 border-l-purple-500"
                        : "hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-gray-900 truncate">
                          {trade.sec_name || trade.symbol}
                        </p>
                        <p className="text-[11px] text-gray-400 mt-0.5 truncate">
                          {trade.person_name}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span
                          className={`inline-flex items-center gap-0.5 text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                            isAcquisition
                              ? "bg-green-50 text-green-700"
                              : "bg-red-50 text-red-700"
                          }`}
                        >
                          {isAcquisition ? (
                            <ArrowUpRight size={11} />
                          ) : (
                            <ArrowDownRight size={11} />
                          )}
                          {trade.trans_type}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {formatValue(trade.trans_value)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
                      <span>{trade.person_cat}</span>
                      <span>·</span>
                      <span>{trade.mode_acq}</span>
                      <span>·</span>
                      <span>{trade.exchange}</span>
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
                {selected.sec_name || selected.symbol}
              </h2>
              <p className="text-xs text-gray-400 mb-6">
                {selected.symbol} · {selected.exchange} · Reported:{" "}
                {selected.reported_to_exchange
                  ? format(
                      parseISO(selected.reported_to_exchange),
                      "d MMM yyyy"
                    )
                  : "—"}
              </p>

              {/* Person info */}
              <div className="bg-gray-50 rounded-xl p-4 mb-5">
                <h3 className="text-[11px] text-gray-400 uppercase tracking-wide mb-2">
                  Insider Details
                </h3>
                <p className="text-sm font-semibold text-gray-900">
                  {selected.person_name}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {selected.person_cat}
                </p>
              </div>

              {/* Transaction details */}
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">
                    Transaction
                  </p>
                  <p className="text-sm font-bold text-gray-900">
                    {selected.trans_type}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {selected.mode_acq}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">
                    Value
                  </p>
                  <p className="text-sm font-bold text-gray-900">
                    {formatValue(selected.trans_value)}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {selected.trans_sec_num?.toLocaleString()} shares
                  </p>
                </div>
              </div>

              {/* Pre & Post holding */}
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div className="border border-gray-200 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-2">
                    Pre-Transaction
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selected.pre_sec_num?.toLocaleString()} shares
                  </p>
                  <p className="text-xs text-gray-500">
                    {selected.pre_sec_pct?.toFixed(2)}% holding
                  </p>
                </div>
                <div className="border border-gray-200 rounded-xl p-4">
                  <p className="text-[11px] text-gray-400 uppercase tracking-wide mb-2">
                    Post-Transaction
                  </p>
                  <p className="text-sm font-semibold text-gray-900">
                    {selected.post_sec_num?.toLocaleString()} shares
                  </p>
                  <p className="text-xs text-gray-500">
                    {selected.post_sec_pct?.toFixed(2)}% holding
                  </p>
                </div>
              </div>

              {/* Dates */}
              <div className="border-t border-gray-100 pt-4 flex flex-wrap gap-x-6 gap-y-2 text-[11px] text-gray-400">
                <span>
                  From:{" "}
                  <span className="text-gray-600 font-medium">
                    {selected.date_from || "—"}
                  </span>
                </span>
                <span>
                  To:{" "}
                  <span className="text-gray-600 font-medium">
                    {selected.date_to || "—"}
                  </span>
                </span>
                <span>
                  Intimation:{" "}
                  <span className="text-gray-600 font-medium">
                    {selected.date_intimation || "—"}
                  </span>
                </span>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <UserCheck size={32} className="mb-3 text-gray-300" />
              <p className="text-sm">Select a trade to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
