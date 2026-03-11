"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  getCorporateFilings,
  getWatchlists,
  type Filing,
  type Watchlist,
} from "@/lib/api";
import { format, parseISO } from "date-fns";
import { Settings, ChevronDown, X } from "lucide-react";
import Link from "next/link";
import { AnnouncementDetail } from "@/components/announcement-detail-new";

function formatTime(dateStr: string) {
  try {
    const d = parseISO(dateStr);
    return format(d, "d MMM, HH:mm") + " IST";
  } catch {
    return dateStr;
  }
}

export default function DashboardPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedWatchlist, setSelectedWatchlist] = useState("all");
  const [wlOpen, setWlOpen] = useState(false);
  const [selectedFiling, setSelectedFiling] = useState<Filing | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  // Fetch watchlists once on mount
  useEffect(() => {
    if (!token) return;
    getWatchlists(token)
      .then((res) => setWatchlists(res.watchlists ?? []))
      .catch(() => {});
  }, [token]);

  const fetchFilings = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const today = new Date().toISOString().slice(0, 10);

      // Build params with watchlist filter
      const params: Record<string, any> = {
        page: 1,
        page_size: 8,
        start_date: today,
        end_date: today,
      };

      if (selectedWatchlist === "all") {
        params.watchlist = true;
      } else {
        // Specific watchlist — pass its ISINs
        const wl = watchlists.find((w) => w._id === selectedWatchlist);
        if (wl?.isin?.length) {
          params.isin = wl.isin.join(",");
        }
      }

      const filRes = await getCorporateFilings(token, params);
      setFilings(filRes.filings.slice(0, 8));
    } catch (err) {
      console.error("Failed to fetch:", err);
    } finally {
      setLoading(false);
    }
  }, [token, selectedWatchlist, watchlists]);

  useEffect(() => {
    fetchFilings();
  }, [fetchFilings]);

  const wlLabel =
    selectedWatchlist === "all"
      ? "All Watchlists"
      : watchlists.find((w) => w._id === selectedWatchlist)?.watchlistName ??
        "All Watchlists";

  return (
    <div className="h-full overflow-y-auto bg-gray-50/50">
      {/* Top bar */}
      <div className="px-6 py-4 flex items-center justify-between bg-white border-b border-gray-100">
        {/* Watchlist selector */}
        <div className="relative">
          <button
            onClick={() => setWlOpen(!wlOpen)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
          >
            {wlLabel}
            <ChevronDown size={14} className="text-gray-400" />
          </button>
          {wlOpen && (
            <div className="absolute top-full left-0 mt-1 w-52 bg-white border border-gray-200 rounded-lg shadow-lg z-30 py-1">
              <button
                onClick={() => {
                  setSelectedWatchlist("all");
                  setWlOpen(false);
                }}
                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                  selectedWatchlist === "all"
                    ? "text-orange-600 font-medium"
                    : "text-gray-700"
                }`}
              >
                All Watchlists
              </button>
              {watchlists.map((wl) => (
                <button
                  key={wl._id}
                  onClick={() => {
                    setSelectedWatchlist(wl._id);
                    setWlOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                    selectedWatchlist === wl._id
                      ? "text-orange-600 font-medium"
                      : "text-gray-700"
                  }`}
                >
                  {wl.watchlistName}
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={() => router.push("/dashboard/watchlists")}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition"
        >
          <Settings size={14} />
          Manage Watchlist
        </button>
      </div>

      {/* Dashboard grid */}
      <div className="p-6">
        <div className="grid grid-cols-12 gap-5">
          {/* ── Announcements card (left, spans 7 cols) ── */}
          <div className="col-span-7 bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">
                Announcements
              </h2>
              <Link
                href="/dashboard/market-feed"
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
              >
                View All
              </Link>
            </div>
            <div className="divide-y divide-gray-50">
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : filings.length === 0 ? (
                <div className="py-12 text-center text-sm text-gray-400">
                  No announcements
                </div>
              ) : (
                filings.map((f, idx) => (
                  <button
                    key={`${f.corp_id}-${idx}`}
                    onClick={() => {
                      setSelectedFiling(f);
                      setPanelOpen(true);
                    }}
                    className="w-full text-left px-5 py-3 hover:bg-gray-50 transition"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-gray-900">
                          {f.companyname}
                        </p>
                        <p className="text-[12px] text-gray-500 line-clamp-1 mt-0.5">
                          {f.headline || f.summary}
                        </p>
                      </div>
                      <span className="text-[11px] text-gray-400 whitespace-nowrap shrink-0 pt-0.5">
                        {formatTime(f.date)}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* ── Right column (5 cols) ── */}
          <div className="col-span-5 flex flex-col gap-5">
            {/* Upcoming Results */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
                <h2 className="text-sm font-bold text-gray-900">
                  Upcoming Results
                </h2>
                <span className="text-xs text-blue-600 font-medium cursor-pointer">
                  View All
                </span>
              </div>
              <div className="px-5 py-4">
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <div className="w-10 h-10 bg-purple-50 rounded-lg flex flex-col items-center justify-center shrink-0">
                    <span className="text-[9px] font-bold text-purple-600 uppercase leading-none">
                      JUL
                    </span>
                    <span className="text-sm font-bold text-purple-700 leading-none">
                      29
                    </span>
                  </div>
                  <span className="text-sm text-gray-700">
                    HDFC Bank Ltd
                  </span>
                </div>
              </div>
            </div>

            {/* Upcoming Concall */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
                <h2 className="text-sm font-bold text-gray-900">
                  Upcoming Concall
                </h2>
                <span className="text-xs text-blue-600 font-medium cursor-pointer">
                  View All
                </span>
              </div>
              <div className="px-5 py-4">
                <div className="flex items-center gap-3 text-sm text-gray-500">
                  <div className="w-10 h-10 bg-blue-50 rounded-lg flex flex-col items-center justify-center shrink-0">
                    <span className="text-[9px] font-bold text-blue-600 uppercase leading-none">
                      JUL
                    </span>
                    <span className="text-sm font-bold text-blue-700 leading-none">
                      29
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-700">HDFC Bank Ltd</p>
                    <p className="text-[11px] text-gray-400">22:30 IST</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Movers & Shakers + Latest Financial Results (side by side) */}
            <div className="grid grid-cols-2 gap-5">
              {/* Movers & Shakers */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <h2 className="text-sm font-bold text-gray-900">
                    Movers & Shakers
                  </h2>
                  <span className="text-xs text-blue-600 font-medium cursor-pointer">
                    View All
                  </span>
                </div>
                <div className="px-4 py-3">
                  <div className="flex items-center gap-4 mb-3">
                    <span className="text-xs font-medium text-green-600 cursor-pointer">
                      Top Gainers
                    </span>
                    <span className="text-xs font-medium text-red-600 cursor-pointer">
                      Top Losers
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">HDFC Bank Ltd</span>
                    <span className="text-red-600 font-medium text-xs">
                      -4.1%
                    </span>
                  </div>
                </div>
              </div>

              {/* Latest Financial Results */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <h2 className="text-sm font-bold text-gray-900">
                    Latest Financial Results
                  </h2>
                  <span className="text-xs text-blue-600 font-medium cursor-pointer">
                    View All
                  </span>
                </div>
                <div className="px-4 py-4 text-xs text-gray-400 text-center">
                  Coming soon
                </div>
              </div>
            </div>

            {/* Corporate Actions */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
                <h2 className="text-sm font-bold text-gray-900">
                  Corporate Actions
                </h2>
                <span className="text-xs text-blue-600 font-medium cursor-pointer">
                  View All
                </span>
              </div>
              <div className="divide-y divide-gray-50">
                <div className="flex items-center gap-3 px-5 py-3">
                  <div className="w-10 h-10 bg-teal-50 rounded-lg flex flex-col items-center justify-center shrink-0">
                    <span className="text-[9px] font-bold text-teal-600 uppercase leading-none">
                      SEPT
                    </span>
                    <span className="text-sm font-bold text-teal-700 leading-none">
                      01
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-700 font-medium">
                      HDFC Bank Ltd
                    </p>
                    <p className="text-[11px] text-gray-400">
                      Annual General Meeting
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 px-5 py-3">
                  <div className="w-10 h-10 bg-orange-50 rounded-lg flex flex-col items-center justify-center shrink-0">
                    <span className="text-[9px] font-bold text-orange-600 uppercase leading-none">
                      AUG
                    </span>
                    <span className="text-sm font-bold text-orange-700 leading-none">
                      10
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-700 font-medium">
                      HDFC Bank Ltd
                    </p>
                    <p className="text-[11px] text-gray-400">
                      Interim Dividend - Rs 15 per share
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Announcement Detail Side Panel ── */}
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/20 z-40 transition-opacity duration-300 ${
          panelOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setPanelOpen(false)}
      />

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[52%] max-w-[720px] bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] ${
          panelOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-gray-100 shrink-0">
          <h3 className="text-sm font-bold text-gray-900 truncate pr-4">
            {selectedFiling?.companyname}
          </h3>
          <button
            onClick={() => setPanelOpen(false)}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition text-gray-400 hover:text-gray-600"
          >
            <X size={16} />
          </button>
        </div>

        {/* Detail content */}
        <div className="flex-1 overflow-y-auto">
          {selectedFiling && (
            <AnnouncementDetail filing={selectedFiling} />
          )}
        </div>
      </div>
    </div>
  );
}
