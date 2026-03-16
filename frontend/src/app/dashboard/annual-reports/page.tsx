"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { getCorporateFilings } from "@/lib/api";
import type { Filing } from "@/lib/api";
import { AnnouncementList } from "@/components/announcement-list-new";
import { AnnouncementDetail } from "@/components/announcement-detail-new";
import { FileSpreadsheet, RefreshCcw, ArrowLeft } from "lucide-react";
import { FeedNavStrip } from "@/components/feed-nav-strip";

export default function AnnualReportsPage() {
  const { token } = useAuth();
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [selected, setSelected] = useState<Filing | null>(null);

  const today = new Date().toISOString().slice(0, 10);

  const fetchData = useCallback(
    async (p: number, append = false) => {
      if (!token) return;
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const res = await getCorporateFilings({
          start_date: today,
          end_date: today,
          category: "Annual Report",
          page: p,
        });
        if (append) {
          setFilings((prev) => [...prev, ...(res.filings ?? [])]);
        } else {
          setFilings(res.filings ?? []);
        }
        setTotalCount(res.total_count ?? 0);
        setHasNext(res.has_next);
        setCurrentPage(res.current_page);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [token, today]
  );

  useEffect(() => {
    fetchData(1);
  }, [fetchData]);

  return (
    <div className="flex flex-col h-full">
      <FeedNavStrip />
      <div className="px-4 md:px-6 py-3 md:py-4 border-b border-gray-100 flex items-center justify-between bg-white">
        <div className="flex items-center gap-2">
          {selected && (
            <button
              onClick={() => setSelected(null)}
              className="md:hidden p-1 -ml-1 mr-1 text-gray-500 hover:text-gray-900 transition"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <FileSpreadsheet size={18} className="text-blue-600" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">Annual Reports</h1>
          <span className="text-xs text-gray-400 ml-2">{totalCount.toLocaleString()} reports</span>
        </div>
        <button onClick={() => fetchData(1)} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 transition">
          <RefreshCcw size={14} /> Refresh
        </button>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className={`w-full md:w-[420px] md:shrink-0 border-r border-gray-100 flex flex-col overflow-hidden ${selected ? "hidden md:flex" : "flex"}`}>
          <AnnouncementList filings={filings} loading={loading} selectedId={selected?.corp_id ?? null} onSelect={setSelected} hasNext={hasNext} onLoadMore={() => { if (!loadingMore && hasNext) fetchData(currentPage + 1, true); }} loadingMore={loadingMore} />
        </div>
        <div className={`flex-1 overflow-hidden ${selected ? "flex flex-col" : "hidden md:flex md:flex-col"}`}>
          {selected ? <AnnouncementDetail filing={selected} /> : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <FileSpreadsheet size={32} className="mb-3 text-gray-300" />
              <p className="text-sm">Select a report to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
