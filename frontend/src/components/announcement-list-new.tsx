"use client";

import { format, parseISO } from "date-fns";
import type { Filing } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { getCategoryClasses } from "@/lib/categories";
import { useRef, useCallback, useEffect } from "react";

function formatTime(dateStr: string) {
  try {
    const d = parseISO(dateStr);
    return format(d, "d MMM, HH:mm") + " IST";
  } catch {
    return dateStr;
  }
}

interface Props {
  filings: Filing[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (filing: Filing) => void;
  hasNext: boolean;
  onLoadMore?: () => void;
  loadingMore?: boolean;
  showMoreButton?: boolean;
  onShowMore?: () => void;
  readIds?: Set<string>;
}

export function AnnouncementList({
  filings,
  loading,
  selectedId,
  onSelect,
  hasNext,
  onLoadMore,
  loadingMore,
  showMoreButton,
  onShowMore,
  readIds,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Infinite scroll observer
  useEffect(() => {
    if (showMoreButton || !onLoadMore) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNext && !loading && !loadingMore) {
          onLoadMore();
        }
      },
      { root: scrollRef.current, threshold: 0.1 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasNext, loading, loadingMore, onLoadMore, showMoreButton]);

  if (loading && filings.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-orange-500" />
      </div>
    );
  }

  if (filings.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        No announcements found
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {filings.map((f, idx) => {
          const isReadItem = readIds?.has(f.corp_id) ?? false;
          return (
          <button
            key={`${f.corp_id}-${idx}`}
            onClick={() => onSelect(f)}
            className={`w-full text-left px-5 py-4 border-b border-gray-100 hover:bg-gray-50/80 transition ${
              selectedId === f.corp_id ? "bg-orange-50/60" : ""
            } ${isReadItem && selectedId !== f.corp_id ? "opacity-70" : ""}`}
          >
            {/* Row 1: Company name + time */}
            <div className="flex items-start justify-between gap-3 mb-1">
              <span className="text-[13px] font-bold text-gray-900 leading-snug">
                {f.companyname || f.symbol}
              </span>
              <span className="text-xs text-gray-400 whitespace-nowrap shrink-0">
                {formatTime(f.date)}
              </span>
            </div>

            {/* Row 2: Headline */}
            <p className="text-[13px] text-gray-600 line-clamp-2 leading-snug mb-2">
              {f.headline || f.summary}
            </p>

            {/* Row 3: Category pill + Sentiment on right */}
            <div className="flex items-center justify-between gap-2">
              <span
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${getCategoryClasses(
                  f.category
                )}`}
              >
                {f.category}
              </span>

              {f.sentiment && (
                <span
                  className={`flex items-center gap-1 text-[11px] font-medium shrink-0 ${
                    f.sentiment === "Positive"
                      ? "text-green-600"
                      : f.sentiment === "Negative"
                      ? "text-red-600"
                      : "text-yellow-600"
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      f.sentiment === "Positive"
                        ? "bg-green-500"
                        : f.sentiment === "Negative"
                        ? "bg-red-500"
                        : "bg-yellow-500"
                    }`}
                  />
                  {f.sentiment}
                </span>
              )}
            </div>
          </button>
          );
        })}

        {/* Show more button (for dashboard) */}
        {showMoreButton && (
          <div className="flex justify-center py-4 border-b border-gray-100">
            <button
              onClick={onShowMore}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              Show 20 more announcements
            </button>
          </div>
        )}

        {/* Infinite scroll sentinel */}
        {!showMoreButton && hasNext && (
          <div ref={sentinelRef} className="flex justify-center py-4">
            {loadingMore && (
              <Loader2 className="w-4 h-4 animate-spin text-orange-500" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
