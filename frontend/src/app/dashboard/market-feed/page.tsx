"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { getCorporateFilings, getWatchlists, markFilingsRead } from "@/lib/api";
import type { Filing, FilingsParams, Watchlist } from "@/lib/api";
import { AnnouncementList } from "@/components/announcement-list-new";
import { AnnouncementDetail } from "@/components/announcement-detail-new";
import { Radio, RefreshCcw, X, ChevronDown, ArrowLeft, SlidersHorizontal } from "lucide-react";
import { useFilterStore } from "@/lib/filter-store";
import { useMobileDetailStore } from "@/lib/mobile-detail-store";
import { useNewAnnouncementSocket } from "@/lib/use-socket";
import { format } from "date-fns";
import { DateFilterModal } from "@/components/filters/date-filter-modal";
import { CategoryFilterModal } from "@/components/filters/category-filter-modal";
import { CompanyFilterModal } from "@/components/filters/company-filter-modal";
import { SentimentFilterModal } from "@/components/filters/sentiment-filter-modal";
import { WatchlistFilterModal } from "@/components/filters/watchlist-filter-modal";

export default function MarketFeedPage() {
  const { token } = useAuth();
  const {
    filters,
    selectedCategories,
    selectedSentiments,
    selectedCompanies,
    selectedWatchlistId,
    watchlistOnly,
    setFilters,
    setSelectedCategories,
    setSelectedSentiments,
    setSelectedCompanies,
    setSelectedWatchlistId,
    setWatchlistOnly,
    resetAll: resetFilters,
  } = useFilterStore();

  const { setDetailOpen } = useMobileDetailStore();

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
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [wlOpen, setWlOpen] = useState(false);

  // Mobile filter sheet
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  // Filter modals (shared between sidebar on desktop and mobile sheet)
  const [dateOpen, setDateOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [companyOpen, setCompanyOpen] = useState(false);
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [watchlistFilterOpen, setWatchlistFilterOpen] = useState(false);

  // Derive selectedWatchlist from filter store
  const selectedWatchlist = watchlistOnly
    ? (selectedWatchlistId ?? "all")
    : "none";

  // Load watchlists
  useEffect(() => {
    if (!token) return;
    getWatchlists(token)
      .then((res) => setWatchlists(res.watchlists ?? []))
      .catch(() => {});
  }, [token]);

  // WebSocket new announcement notifications
  const { newCount, resetCount } = useNewAnnouncementSocket();

  // Signal layout when filing detail is open on mobile (for close button in bottom tabs)
  useEffect(() => {
    if (selectedFiling) {
      setDetailOpen(true, () => setSelectedFiling(null));
    } else {
      setDetailOpen(false, null);
    }
    return () => setDetailOpen(false, null);
  }, [selectedFiling, setDetailOpen]);

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
          selectedCompanies.includes(f.isin)
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
          // selectedCompanies now contains ISINs from company filter
          const existingIsins = params.isin ? params.isin.split(",") : [];
          const allIsins = [...new Set([...existingIsins, ...selectedCompanies])];
          params.isin = allIsins.join(",");
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

        // Build read IDs from server-side is_read flag
        const newReadIds = new Set<string>();
        for (const f of newFilings) {
          if (f.is_read) newReadIds.add(f.corp_id);
        }

        if (append) {
          setFilings((prev) => [...prev, ...newFilings]);
          setReadIds((prev) => {
            const merged = new Set(prev);
            newReadIds.forEach((id) => merged.add(id));
            return merged;
          });
        } else {
          setFilings(newFilings);
          setReadIds(newReadIds);
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
    [token, filters, selectedCategories, selectedCompanies, selectedWatchlistId, watchlistOnly, watchlists, showUnread, applyClientFilters]
  );

  // Reset & fetch when filters change
  useEffect(() => {
    filterVersion.current += 1;
    setFilings([]);
    setSelectedFiling(null);
    setCurrentPage(1);
    fetchFilings(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, selectedCategories, selectedSentiments, selectedCompanies, selectedWatchlistId, watchlistOnly, showUnread, token]);

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
      if (filing.corp_id && token) {
        // Optimistically mark as read locally
        setReadIds((prev) => new Set(prev).add(filing.corp_id));
        // Mark as read on the server (fire-and-forget)
        markFilingsRead(token, [filing.corp_id]).catch(() => {});
      }
    },
    [token]
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

  // Count active filters for mobile badge
  const activeFilterCount =
    (selectedCategories.length > 0 ? 1 : 0) +
    (selectedCompanies.length > 0 ? 1 : 0) +
    (selectedSentiments.length > 0 ? 1 : 0) +
    (watchlistOnly ? 1 : 0);

  // Date filter state
  const startDate = filters?.start_date ? new Date(filters.start_date) : null;
  const endDate = filters?.end_date ? new Date(filters.end_date) : null;
  const dateLabel = startDate ? format(startDate, "d MMM") : format(new Date(), "d MMM");

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 md:px-6 py-3 md:py-4 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-2">
          {/* Mobile back button when viewing detail */}
          {selectedFiling && (
            <button
              onClick={() => setSelectedFiling(null)}
              className="md:hidden p-1 -ml-1 mr-1 text-gray-500 hover:text-gray-900 transition"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <Radio size={18} className="text-orange-500" />
          <h1 className="text-base md:text-lg font-bold text-gray-900">
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
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
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
                  onClick={() => { setSelectedWatchlistId(null); setWatchlistOnly(false); setWlOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                    selectedWatchlist === "none" ? "text-orange-600 font-medium" : "text-gray-700"
                  }`}
                >
                  No Filter
                </button>
                <button
                  onClick={() => { setSelectedWatchlistId(null); setWatchlistOnly(true); setWlOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                    selectedWatchlist === "all" ? "text-orange-600 font-medium" : "text-gray-700"
                  }`}
                >
                  All Watchlists
                </button>
                {watchlists.map((wl) => (
                  <button
                    key={wl._id}
                    onClick={() => { setSelectedWatchlistId(wl._id); setWatchlistOnly(true); setWlOpen(false); }}
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
          <label className="hidden md:flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
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
        {/* List panel - full width on mobile, fixed width on desktop */}
        <div className={`w-full md:w-[420px] md:shrink-0 border-r border-gray-100 flex flex-col overflow-hidden relative ${selectedFiling ? "hidden md:flex" : "flex"}`}>
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
              <span className="text-gray-400">&uarr;</span>
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
        {/* Detail panel - full width on mobile, flex-1 on desktop */}
        <div className={`flex-1 overflow-hidden ${selectedFiling ? "flex flex-col" : "hidden md:flex md:flex-col"}`}>
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
