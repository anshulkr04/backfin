"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import {
  LayoutDashboard,
  Bookmark,
  Radio,
  Search,
  ChevronRight,
  LogOut,
  ChevronDown,
  Users,
  FileText,
  BarChart3,
  Phone,
  Presentation,
  FileSpreadsheet,
  Layers,
  UserCheck,
  GitPullRequest,
  X,
  List,
} from "lucide-react";
import { useState, useRef } from "react";
import { format } from "date-fns";
import { DateFilterModal } from "@/components/filters/date-filter-modal";
import { CategoryFilterModal } from "@/components/filters/category-filter-modal";
import { CompanyFilterModal } from "@/components/filters/company-filter-modal";
import { SentimentFilterModal } from "@/components/filters/sentiment-filter-modal";
import { WatchlistFilterModal } from "@/components/filters/watchlist-filter-modal";
import { useFilterStore } from "@/lib/filter-store";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/saved", label: "Saved", icon: Bookmark },
  { href: "/dashboard/market-feed", label: "Market Feed", icon: Radio, hasSubmenu: true },
  { href: "/dashboard/watchlists", label: "Watchlists", icon: List },
  { href: "/dashboard/smart-money", label: "Smart Money", icon: Users },
  { href: "/dashboard/search", label: "Search", icon: Search },
];

const MARKET_FEED_ITEMS = [
  { href: "/dashboard/market-feed", label: "Announcements", description: "All corporate filings and updates.", icon: FileText },
  { href: "/dashboard/financial-results", label: "Financial Results", description: "Quarterly & annual performance.", icon: BarChart3 },
  { href: "/dashboard/concall-transcripts", label: "Concall Transcripts", description: "Management commentary & insights.", icon: Phone },
  { href: "/dashboard/investor-presentations", label: "Investor Presentations", description: "Official company presentations.", icon: Presentation },
  { href: "/dashboard/annual-reports", label: "Annual Reports", description: "Comprehensive yearly reports.", icon: FileSpreadsheet },
  { href: "/dashboard/bulk-block-deals", label: "Bulk & Block Deals", description: "Significant market transactions.", icon: Layers },
  { href: "/dashboard/insider-trades", label: "Insider Trades", description: "Trades by promoters & insiders.", icon: UserCheck },
  { href: "/dashboard/corporate-actions", label: "Corporate Actions", description: "Dividends, splits, and more.", icon: GitPullRequest },
];

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps = {}) {
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
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [showUser, setShowUser] = useState(false);

  // Filter modals
  const [dateOpen, setDateOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [companyOpen, setCompanyOpen] = useState(false);
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [watchlistOpen, setWatchlistOpen] = useState(false);
  const [marketFeedMenuOpen, setMarketFeedMenuOpen] = useState(false);
  const marketFeedBtnRef = useRef<HTMLDivElement>(null);

  // Date filter state
  const startDate = filters?.start_date ? new Date(filters.start_date) : null;
  const endDate = filters?.end_date ? new Date(filters.end_date) : null;
  const dateLabel = startDate ? format(startDate, "d MMM") : format(new Date(), "d MMM");

  const hasAnyFilter =
    (filters?.start_date) ||
    selectedCategories.length > 0 ||
    selectedCompanies.length > 0 ||
    selectedSentiments.length > 0 ||
    watchlistOnly;

  const resetAll = () => {
    resetFilters();
  };

  const isMarketFeed = pathname === "/dashboard/market-feed" ||
    pathname === "/dashboard/financial-results" ||
    pathname === "/dashboard/bulk-block-deals" ||
    pathname === "/dashboard/corporate-actions" ||
    pathname === "/dashboard/insider-trades" ||
    pathname === "/dashboard/concall-transcripts" ||
    pathname === "/dashboard/investor-presentations" ||
    pathname === "/dashboard/annual-reports";

  return (
    <>
      <aside className="w-full md:w-[200px] flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full">
        {/* Logo + mobile close */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <Link href="/dashboard" className="block" onClick={onClose}>
            <Logo variant="full" theme="dark" className="h-6" />
          </Link>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-gray-100 transition text-gray-400 hover:text-gray-600 md:hidden"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : item.hasSubmenu
                ? isMarketFeed
                : pathname.startsWith(item.href);
            return (
              <div key={item.href} className="relative" ref={item.hasSubmenu ? marketFeedBtnRef : undefined}>
                {item.hasSubmenu ? (
                  <button
                    onClick={() => setMarketFeedMenuOpen(true)}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition w-full ${
                      isActive
                        ? "bg-orange-50 text-orange-600"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    }`}
                  >
                    <item.icon size={16} strokeWidth={isActive ? 2 : 1.5} />
                    {item.label}
                    <ChevronRight size={12} className="ml-auto text-gray-400" />
                  </button>
                ) : (
                  <Link
                    href={item.href}
                    onClick={onClose}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
                      isActive
                        ? "bg-orange-50 text-orange-600"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    }`}
                  >
                    <item.icon size={16} strokeWidth={isActive ? 2 : 1.5} />
                    {item.label}
                  </Link>
                )}
              </div>
            );
          })}

          {/* Filters section - only on announcements page */}
          {pathname === "/dashboard/market-feed" && (
            <>
              <div className="pt-5 pb-1 px-3 flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  Filters
                </span>
                {hasAnyFilter && (
                  <button
                    onClick={resetAll}
                    className="text-[11px] text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Reset All
                  </button>
                )}
              </div>

              {/* Date */}
              <button
                onClick={() => setDateOpen(true)}
                className="flex items-center justify-between w-full px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition"
              >
                <span className="font-medium">Date</span>
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  {dateLabel}
                  <ChevronRight size={14} className="text-gray-400" />
                </span>
              </button>

              {/* Company */}
              <button
                onClick={() => setCompanyOpen(true)}
                className="flex items-center justify-between w-full px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition"
              >
                <span className="font-medium">Company</span>
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  {selectedCompanies.length > 0 && (
                    <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
                      {selectedCompanies.length}
                    </span>
                  )}
                  <ChevronRight size={14} className="text-gray-400" />
                </span>
              </button>

              {/* Watchlists */}
              <button
                onClick={() => setWatchlistOpen(true)}
                className="flex items-center justify-between w-full px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition"
              >
                <span className="font-medium">Watchlists</span>
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  {watchlistOnly && (
                    <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
                      On
                    </span>
                  )}
                  <ChevronRight size={14} className="text-gray-400" />
                </span>
              </button>

              {/* Category */}
              <button
                onClick={() => setCategoryOpen(true)}
                className="flex items-center justify-between w-full px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition"
              >
                <span className="font-medium">Category</span>
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  {selectedCategories.length > 0 && (
                    <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
                      {selectedCategories.length}
                    </span>
                  )}
                  <ChevronRight size={14} className="text-gray-400" />
                </span>
              </button>

              {/* Sentiment */}
              <button
                onClick={() => setSentimentOpen(true)}
                className="flex items-center justify-between w-full px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition"
              >
                <span className="font-medium">Sentiment</span>
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  {selectedSentiments.length > 0 && (
                    <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
                      {selectedSentiments.length}
                    </span>
                  )}
                  <ChevronRight size={14} className="text-gray-400" />
                </span>
              </button>
            </>
          )}
        </nav>

        {/* User */}
        <div className="border-t border-gray-100 p-3 relative">
          <button
            onClick={() => setShowUser(!showUser)}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg hover:bg-gray-50 transition"
          >
            <div className="w-7 h-7 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-semibold">
              {user?.emailID?.[0]?.toUpperCase() || "U"}
            </div>
            <span className="text-xs text-gray-600 truncate flex-1 text-left">
              {user?.emailID || "User"}
            </span>
            <ChevronDown size={12} className="text-gray-400" />
          </button>

          {showUser && (
            <div className="absolute bottom-full left-3 right-3 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden z-50">
              <button
                onClick={() => {
                  logout();
                  setShowUser(false);
                }}
                className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 transition"
              >
                <LogOut size={14} />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Filter Modals */}
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
        open={watchlistOpen}
        selectedWatchlistId={selectedWatchlistId}
        watchlistOnly={watchlistOnly}
        onApply={(id, only) => {
          setSelectedWatchlistId(id);
          setWatchlistOnly(only);
        }}
        onClose={() => setWatchlistOpen(false)}
      />

      {/* Market Feed sub-menu popup */}
      {marketFeedMenuOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[8vh]">
          <div
            className="fixed inset-0 bg-black/20"
            onClick={() => setMarketFeedMenuOpen(false)}
          />
          <div className="relative bg-white rounded-xl shadow-2xl w-[calc(100vw-2rem)] max-w-[580px] mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">
                Market Feed
              </h2>
              <button
                onClick={() => setMarketFeedMenuOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {MARKET_FEED_ITEMS.map((mfItem) => (
                  <Link
                    key={mfItem.href}
                    href={mfItem.href}
                    onClick={() => { setMarketFeedMenuOpen(false); onClose?.(); }}
                    className="flex items-start gap-3.5 p-4 rounded-xl hover:bg-gray-50 transition group"
                  >
                    <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center shrink-0 group-hover:bg-gray-200 transition">
                      <mfItem.icon
                        size={20}
                        className="text-gray-500 group-hover:text-gray-700"
                      />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900 group-hover:text-gray-900">
                        {mfItem.label}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                        {mfItem.description}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
