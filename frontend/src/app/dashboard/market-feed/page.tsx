"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { getCorporateFilings, getWatchlists, markFilingsRead, getReadStatus, type Filing, FilingsParams, Watchlist } from "@/lib/api";
import { AnnouncementList } from "@/components/announcement-list-new";
import { AnnouncementDetail } from "@/components/announcement-detail-new";
import { Radio, RefreshCcw, X, ArrowLeft, SlidersHorizontal, ChevronRight, Calendar, Building2, Tag, TrendingUp, List } from "lucide-react";
import { useFilterStore } from "@/lib/filter-store";
import { useMobileDetailStore } from "@/lib/mobile-detail-store";
import { useNewAnnouncementSocket } from "@/lib/use-socket";
import { format } from "date-fns";
import { DateFilterModal } from "@/components/filters/date-filter-modal";
import { CategoryFilterModal } from "@/components/filters/category-filter-modal";
import { CompanyFilterModal } from "@/components/filters/company-filter-modal";
import { SentimentFilterModal } from "@/components/filters/sentiment-filter-modal";
import { WatchlistFilterModal } from "@/components/filters/watchlist-filter-modal";
import { FeedNavStrip } from "@/components/feed-nav-strip";

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
  const [activeCategoryLabel, setActiveCategoryLabel] = useState<string | null>(null);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());

  // Mobile filter sheet
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  // Filter modals (shared between sidebar on desktop and mobile sheet)
  const [dateOpen, setDateOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [companyOpen, setCompanyOpen] = useState(false);
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [watchlistFilterOpen, setWatchlistFilterOpen] = useState(false);

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
          const existingIsins = params.isin ? params.isin.split(",") : [];
          const allIsins = [...new Set([...existingIsins, ...selectedCompanies])];
          params.isin = allIsins.join(",");
        }

        // Watchlist filter — use server-side V2 watchlist param
        if (watchlistOnly) {
          params.watchlist = true;
        }

        const res = await getCorporateFilings(params, token);
        const newFilings = applyClientFilters(res.filings ?? []);

        if (append) {
          setFilings((prev) => [...prev, ...newFilings]);
        } else {
          setFilings(newFilings);
        }
        setTotalCount(res.total_count ?? 0);
        setCurrentPage(res.current_page);
        setHasNext(res.has_next);

        // Fetch read status for the returned filings
        const corpIds = newFilings.map((f) => f.corp_id);
        if (corpIds.length > 0) {
          try {
            const statusRes = await getReadStatus(token, corpIds);
            const newReadIds = new Set(statusRes.read_corp_ids ?? []);
            if (append) {
              setReadIds((prev) => new Set([...prev, ...newReadIds]));
            } else {
              setReadIds(newReadIds);
            }
          } catch {
            // Read status is non-critical
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [token, filters, selectedCategories, selectedCompanies, selectedWatchlistId, watchlistOnly, applyClientFilters]
  );

  // Reset & fetch when filters change
  useEffect(() => {
    filterVersion.current += 1;
    setFilings([]);
    setSelectedFiling(null);
    setCurrentPage(1);
    fetchFilings(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, selectedCategories, selectedSentiments, selectedCompanies, selectedWatchlistId, watchlistOnly, token]);

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
      // Mark as read
      if (token && !readIds.has(filing.corp_id)) {
        markFilingsRead(token, [filing.corp_id])
          .then(() => setReadIds((prev) => new Set([...prev, filing.corp_id])))
          .catch(() => {});
      }
    },
    [token, readIds]
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

  // Has any active date filter?
  const hasDateFilter = !!(filters?.start_date);

  return (
    <div className="flex flex-col h-full">
      {/* Mobile feed type navigation strip */}
      <FeedNavStrip />

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
          <span className="text-xs text-gray-400 ml-2 hidden md:inline">
            {totalCount.toLocaleString()} announcements
          </span>
        </div>
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
          {/* Mobile filter trigger button */}
          <button
            onClick={() => setMobileFilterOpen(true)}
            className="md:hidden relative flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 transition"
          >
            <SlidersHorizontal size={14} />
            Filters
            {activeFilterCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 flex items-center justify-center w-4 h-4 bg-orange-500 text-white text-[10px] font-bold rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Refresh & auto-refresh */}
          <button
            onClick={() => {
              setFilings([]);
              setCurrentPage(1);
              fetchFilings(1, false);
            }}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 transition"
          >
            <RefreshCcw size={14} />
            <span className="hidden md:inline">Refresh</span>
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

      {/* ── Mobile filter bottom sheet ── */}
      {mobileFilterOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-black/30"
            onClick={() => setMobileFilterOpen(false)}
          />
          <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl safe-area-bottom animate-in slide-in-from-bottom duration-200">
            {/* Handle bar */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 bg-gray-300 rounded-full" />
            </div>
            {/* Header */}
            <div className="flex items-center justify-between px-5 pb-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">Filters</h3>
              <div className="flex items-center gap-3">
                {(activeFilterCount > 0 || hasDateFilter) && (
                  <button
                    onClick={() => {
                      resetFilters();
                      setMobileFilterOpen(false);
                    }}
                    className="text-xs text-blue-600 font-medium"
                  >
                    Reset All
                  </button>
                )}
                <button
                  onClick={() => setMobileFilterOpen(false)}
                  className="p-1 text-gray-400 hover:text-gray-600"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            {/* Filter options */}
            <div className="px-4 py-3 space-y-1">
              {/* Date */}
              <button
                onClick={() => { setMobileFilterOpen(false); setDateOpen(true); }}
                className="flex items-center justify-between w-full px-3 py-3 hover:bg-gray-50 rounded-xl transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Calendar size={16} className="text-blue-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-800">Date</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">{dateLabel}</span>
                  <ChevronRight size={16} className="text-gray-400" />
                </div>
              </button>

              {/* Company */}
              <button
                onClick={() => { setMobileFilterOpen(false); setCompanyOpen(true); }}
                className="flex items-center justify-between w-full px-3 py-3 hover:bg-gray-50 rounded-xl transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center">
                    <Building2 size={16} className="text-purple-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-800">Company</span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedCompanies.length > 0 && (
                    <span className="bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                      {selectedCompanies.length}
                    </span>
                  )}
                  <ChevronRight size={16} className="text-gray-400" />
                </div>
              </button>

              {/* Watchlists */}
              <button
                onClick={() => { setMobileFilterOpen(false); setWatchlistFilterOpen(true); }}
                className="flex items-center justify-between w-full px-3 py-3 hover:bg-gray-50 rounded-xl transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center">
                    <List size={16} className="text-green-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-800">Watchlists</span>
                </div>
                <div className="flex items-center gap-2">
                  {watchlistOnly && (
                    <span className="bg-green-50 text-green-600 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                      On
                    </span>
                  )}
                  <ChevronRight size={16} className="text-gray-400" />
                </div>
              </button>

              {/* Category */}
              <button
                onClick={() => { setMobileFilterOpen(false); setCategoryOpen(true); }}
                className="flex items-center justify-between w-full px-3 py-3 hover:bg-gray-50 rounded-xl transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                    <Tag size={16} className="text-amber-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-800">Category</span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedCategories.length > 0 && (
                    <span className="bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                      {selectedCategories.length}
                    </span>
                  )}
                  <ChevronRight size={16} className="text-gray-400" />
                </div>
              </button>

              {/* Sentiment */}
              <button
                onClick={() => { setMobileFilterOpen(false); setSentimentOpen(true); }}
                className="flex items-center justify-between w-full px-3 py-3 hover:bg-gray-50 rounded-xl transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-rose-50 flex items-center justify-center">
                    <TrendingUp size={16} className="text-rose-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-800">Sentiment</span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedSentiments.length > 0 && (
                    <span className="bg-rose-50 text-rose-600 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                      {selectedSentiments.length}
                    </span>
                  )}
                  <ChevronRight size={16} className="text-gray-400" />
                </div>
              </button>
            </div>
            {/* Bottom spacing for safe area */}
            <div className="h-4" />
          </div>
        </div>
      )}

      {/* ── Filter Modals (rendered here for mobile; sidebar renders its own for desktop) ── */}
      <DateFilterModal
        open={dateOpen}
        startDate={startDate}
        endDate={endDate}
        onApply={(s, e) => {
          setFilters({
            ...filters,
            start_date: s ? format(s, "yyyy-MM-dd") : undefined,
            end_date: e ? format(e, "yyyy-MM-dd") : undefined,
          });
        }}
        onClose={() => setDateOpen(false)}
      />
      <CategoryFilterModal
        open={categoryOpen}
        selected={selectedCategories}
        onApply={(cats) => setSelectedCategories(cats)}
        onClose={() => setCategoryOpen(false)}
      />
      <CompanyFilterModal
        open={companyOpen}
        selectedSymbols={selectedCompanies}
        onApply={(syms) => setSelectedCompanies(syms)}
        onClose={() => setCompanyOpen(false)}
      />
      <SentimentFilterModal
        open={sentimentOpen}
        selected={selectedSentiments}
        onApply={(sents) => setSelectedSentiments(sents)}
        onClose={() => setSentimentOpen(false)}
      />
      <WatchlistFilterModal
        open={watchlistFilterOpen}
        selectedWatchlistId={selectedWatchlistId}
        watchlistOnly={watchlistOnly}
        onApply={(id, only) => {
          setSelectedWatchlistId(id);
          setWatchlistOnly(only);
        }}
        onClose={() => setWatchlistFilterOpen(false)}
      />
    </div>
  );
}
