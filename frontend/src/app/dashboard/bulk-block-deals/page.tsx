"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { getDeals } from "@/lib/api";
import type { Deal } from "@/lib/api";
import { Layers, RefreshCcw, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { format, parseISO } from "date-fns";
import { InlineDatePicker } from "@/components/inline-date-picker";

export default function BulkBlockDealsPage() {
  const { token } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [filterDeal, setFilterDeal] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");

  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [fetchKey, setFetchKey] = useState(0);

  // Fetch data when filters change
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    getDeals(token, {
      start_date: startDate,
      end_date: endDate,
      deal: filterDeal || undefined,
      deal_type: filterType || undefined,
      page: 1,
      page_size: 50,
    }).then((res) => {
      if (cancelled) return;
      setDeals(res.deals);
      setTotalCount(res.pagination.total_count);
      setHasNext(res.pagination.has_next);
      setPage(res.pagination.page);
    }).catch((err) => {
      if (!cancelled) console.error("Failed to fetch deals:", err);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [token, startDate, endDate, filterDeal, filterType, fetchKey]);

  const handleLoadMore = () => {
    if (!hasNext || !token) return;
    getDeals(token, {
      start_date: startDate,
      end_date: endDate,
      deal: filterDeal || undefined,
      deal_type: filterType || undefined,
      page: page + 1,
      page_size: 50,
    }).then((res) => {
      setDeals((prev) => [...prev, ...res.deals]);
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
          <Layers size={18} className="text-emerald-500" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">
            Bulk & Block Deals
          </h1>
          <span className="text-xs text-gray-400 ml-2">
            {totalCount.toLocaleString()} deals
          </span>
        </div>
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
          {/* Deal type filter */}
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
            {["", "BULK", "BLOCK"].map((d) => (
              <button
                key={d}
                onClick={() => setFilterDeal(d)}
                className={`px-3 py-1.5 text-xs font-medium transition ${
                  filterDeal === d
                    ? "bg-gray-900 text-white"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {d || "All"}
              </button>
            ))}
          </div>
          {/* Buy/Sell filter */}
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
            {["", "BUY", "SELL"].map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-3 py-1.5 text-xs font-medium transition ${
                  filterType === t
                    ? "bg-gray-900 text-white"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {t || "All"}
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
            <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : deals.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-400">
            No deals found for today
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
                  Client
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Type
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Deal
                </th>
                <th className="text-right px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Qty
                </th>
                <th className="text-right px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Price
                </th>
                <th className="text-center px-3 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Exchange
                </th>
                <th className="text-right px-5 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {deals.map((deal) => (
                <tr
                  key={deal.id}
                  className="hover:bg-gray-50 transition"
                >
                  <td className="px-5 py-3 font-semibold text-gray-900">
                    {deal.symbol}
                  </td>
                  <td className="px-3 py-3 text-gray-600 max-w-[200px] truncate">
                    {deal.client_name}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span
                      className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${
                        deal.deal_type === "BUY"
                          ? "bg-green-50 text-green-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {deal.deal_type === "BUY" ? (
                        <ArrowUpRight size={11} />
                      ) : (
                        <ArrowDownRight size={11} />
                      )}
                      {deal.deal_type}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                      {deal.deal}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right text-gray-700 font-medium">
                    {deal.quantity.toLocaleString()}
                  </td>
                  <td className="px-3 py-3 text-right text-gray-700">
                    ₹{parseFloat(deal.price).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className="text-[11px] font-medium text-gray-500">
                      {deal.exchange}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right text-gray-400 text-[12px]">
                    {deal.date}
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
