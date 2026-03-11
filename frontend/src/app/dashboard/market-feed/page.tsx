"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { getCorporateFilings, getWatchlists } from "@/lib/api";
import type { Filing, FilingsParams, Watchlist } from "@/lib/api";
import { AnnouncementList } from "@/components/announcement-list-new";
import { AnnouncementDetail } from "@/components/announcement-detail-new";
import { Radio, RefreshCcw, X, ChevronDown } from "lucide-react";
import { useFilterStore } from "@/lib/filter-store";
import { useNewAnnouncementSocket } from "@/lib/use-socket";
import { markAsRead, getReadIds } from "@/lib/read-tracker";

export default function MarketFeedPage() {
  const { token } = useAuth();
  const {
    filters,
    selectedCategories,
    selectedSentiments,
    selectedCompanies,
    setSelectedCategories,
  } = useFilterStore();

  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [selectedFiling, setSelectedFiling] = useState<Filing | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showUnread, setShowUnread] = useState(false);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [activeCategoryLabel, setActiveCategoryLabel] = useState<string | null>(null);

  // Watchlist state
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedWatchlist, setSelectedWatchlist] = useState<string>("none"); // "none" | "all" | watchlist._id
  const [wlOpen, setWlOpen] = useState(false);

  // Load read IDs from localStorage on mount
  useEffect(() => {
    setReadIds(getReadIds());
  }, []);

  // Load watchlists
  useEffect(() => {
    if (!token) return;
    getWatchlists(token)
      .then((res) => setWatchlists(res.watchlists ?? []))
      .catch(() => {});
  }, [token]);

  // WebSocket new announcement notifications
  const { newCount, resetCount } = useNewAnnouncementSocket();

  // Track filter version to reset on change
  const filterVersion = useRef(0);

  const applyClientFilters = useCallback(
    (list: Filing[]) => {
      let filtered = list;
      if (selectedSentiments.length > 0) {
        filtered = filtered.filter(
          (f) => f.sentiment && selectedSentiments.includes(f.sentiment)
        );
      }
      if (selectedCategories.length > 1) {
        filtered = filtered.filter((f) =>
          selectedCategories.includes(f.category)
        );
      }
      if (selectedCompanies.length > 1) {
        filtered = filtered.filter((f) =>
          selectedCompanies.includes(f.symbol)
        );
      }
      return filtered;
    },
    [selectedCategories, selectedSentiments, selectedCompanies]
  );

  const fetchFilings = useCallback(
    async (page: number, append = false) => {
      if (!token) return;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      try {
        const params: FilingsParams = { ...filters, page };

        // Category filter
        if (selectedCategories.length > 0) {
          params.category = selectedCategories.join(",");
        }
        if (selectedCompanies.length > 0) {
          params.symbol = selectedCompanies.join(",");
        }

        // Watchlist filter
        if (selectedWatchlist === "all") {
          params.watchlist = true;
        } else if (selectedWatchlist !== "none") {
          // Specific watchlist — pass its ISINs
          const wl = watchlists.find((w) => w._id === selectedWatchlist);
          if (wl?.isin?.length) {
            params.isin = wl.isin.join(",");
          }
        }

        // Read/unread filter (server-side via V2)
        if (showUnread) {
          params.read_filter = "unread";
        }

        const res = await getCorporateFilings(token, params);
        const newFilings = applyClientFilters(res.filings ?? []);

        if (append) {
          setFilings((prev) => [...prev, ...newFilings]);
        } else {
          setFilings(newFilings);
        }
        setTotalCount(res.total_count ?? 0);
        setCurrentPage(res.current_page);
        setHasNext(res.has_next);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [token, filters, selectedCategories, selectedCompanies, selectedWatchlist, watchlists, showUnread, applyClientFilters]
  );

  // Reset & fetch when filters change
  useEffect(() => {
    filterVersion.current += 1;
    setFilings([]);
    setSelectedFiling(null);
    setCurrentPage(1);
    fetchFilings(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, selectedCategories, selectedSentiments, selectedCompanies, selectedWatchlist, showUnread, token]);

  // Auto-refresh every 60s if enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => fetchFilings(1, false), 60_000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchFilings]);

  const handleLoadMore = useCallback(() => {
    if (loadingMore || !hasNext) return;
    const nextPage = currentPage + 1;
    setCurrentPage(nextPage);
    fetchFilings(nextPage, true);
  }, [loadingMore, hasNext, currentPage, fetchFilings]);

  const handleNewAnnouncementClick = useCallback(() => {
    resetCount();
    setFilings([]);
    setCurrentPage(1);
    fetchFilings(1, false);
  }, [resetCount, fetchFilings]);

  const handleSelectFiling = useCallback(
    (filing: Filing) => {
      setSelectedFiling(filing);
      if (filing.corp_id) {
        markAsRead(filing.corp_id);
        setReadIds((prev) => new Set(prev).add(filing.corp_id));
      }
    },
    []
  );

  const handleCategoryFilter = useCallback(
    (category: string) => {
      setSelectedCategories([category]);
      setActiveCategoryLabel(category);
      setSelectedFiling(null);
    },
    [setSelectedCategories]
  );

  const clearCategoryFilter = useCallback(() => {
    setSelectedCategories([]);
    setActiveCategoryLabel(null);
  }, [setSelectedCategories]);

  const wlLabel =
    selectedWatchlist === "none"
      ? "No Filter"
      : selectedWatchlist === "all"
      ? "All Watchlists"
      : watchlists.find((w) => w._id === selectedWatchlist)?.watchlistName ?? "Watchlist";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio size={18} className="text-orange-500" />
          <h1 className="text-lg font-bold text-gray-900">
            {activeCategoryLabel || "Live Market Feed"}
          </h1>
          {activeCategoryLabel && (
            <button
              onClick={clearCategoryFilter}
              className="ml-1 text-gray-400 hover:text-gray-600 transition"
              title="Clear category filter"
            >
              <X size={14} />
            </button>
          )}
          <span className="text-xs text-gray-400 ml-2">
            {totalCount.toLocaleString()} announcements
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Watchlist filter dropdown */}
          <div className="relative">
            <button
              onClick={() => setWlOpen(!wlOpen)}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 transition"
            >
              {wlLabel}
              <ChevronDown size={12} className="text-gray-400" />
            </button>
            {wlOpen && (
              <div className="absolute top-full right-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-30 py-1">
                <button
                  onClick={() => { setSelectedWatchlist("none"); setWlOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                    selectedWatchlist === "none" ? "text-orange-600 font-medium" : "text-gray-700"
                  }`}
                >
                  No Filter
                </button>
                <button
                  onClick={() => { setSelectedWatchlist("all"); setWlOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                    selectedWatchlist === "all" ? "text-orange-600 font-medium" : "text-gray-700"
                  }`}
                >
                  All Watchlists
                </button>
                {watchlists.map((wl) => (
                  <button
                    key={wl._id}
                    onClick={() => { setSelectedWatchlist(wl._id); setWlOpen(false); }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                      selectedWatchlist === wl._id ? "text-orange-600 font-medium" : "text-gray-700"
                    }`}
                  >
                    {wl.watchlistName}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Read/Unread toggle */}
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowUnread(false)}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                !showUnread
                  ? "bg-gray-900 text-white"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setShowUnread(true)}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                showUnread
                  ? "bg-gray-900 text-white"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Unread
            </button>
          </div>

          <button
            onClick={() => {
              setFilings([]);
              setCurrentPage(1);
              fetchFilings(1, false);
            }}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 transition"
          >
            <RefreshCcw size={14} />
            Refresh
          </button>
          <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-orange-500 focus:ring-orange-500"
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-[420px] shrink-0 border-r border-gray-100 flex flex-col overflow-hidden relative">
          {/* Floating new announcement pill */}
          {newCount > 0 && (
            <button
              onClick={handleNewAnnouncementClick}
              className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-full text-xs font-medium shadow-lg hover:bg-gray-800 transition-all"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500" />
              </span>
              {newCount} new {newCount > 1 ? "announcements" : "announcement"}
              <span className="text-gray-400">↑</span>
            </button>
          )}
          <AnnouncementList
            filings={filings}
            loading={loading}
            selectedId={selectedFiling?.corp_id ?? null}
            onSelect={handleSelectFiling}
            hasNext={hasNext}
            onLoadMore={handleLoadMore}
            loadingMore={loadingMore}
            readIds={readIds}
          />
        </div>
        <div className="flex-1 overflow-hidden">
          {selectedFiling ? (
            <AnnouncementDetail filing={selectedFiling} onCategoryFilter={handleCategoryFilter} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <Radio size={32} className="mb-3 text-gray-300" />
              <p className="text-sm">Select an announcement to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
