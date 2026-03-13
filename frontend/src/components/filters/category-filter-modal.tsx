"use client";

import { useState, useMemo, useEffect } from "react";
import { X, Search } from "lucide-react";
import {
  CATEGORY_GROUPS,
  PROCEDURAL_CATEGORY,
  getCategoryClasses,
} from "@/lib/categories";
import { getAnnouncementCount } from "@/lib/api";
import { useFilterStore } from "@/lib/filter-store";

interface Props {
  open: boolean;
  selected: string[];
  onApply: (cats: string[]) => void;
  onClose: () => void;
}

export function CategoryFilterModal({
  open,
  selected,
  onApply,
  onClose,
}: Props) {
  const [local, setLocal] = useState<string[]>(selected);
  const [search, setSearch] = useState("");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loadingCounts, setLoadingCounts] = useState(false);
  const [includeProcedural, setIncludeProcedural] = useState(false);
  const filters = useFilterStore((s) => s.filters);

  // reset local state when opened
  useMemo(() => {
    if (open) {
      setLocal(selected);
      setSearch("");
      setIncludeProcedural(selected.includes(PROCEDURAL_CATEGORY));
    }
  }, [open, selected]);

  // Fetch category counts when modal opens
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingCounts(true);
    const startDate = filters.start_date || new Date().toISOString().slice(0, 10);
    const endDate = filters.end_date || new Date().toISOString().slice(0, 10);
    getAnnouncementCount(startDate, endDate)
      .then((res) => {
        if (!cancelled) setCounts(res.total_counts || {});
      })
      .catch(() => {
        if (!cancelled) setCounts({});
      })
      .finally(() => {
        if (!cancelled) setLoadingCounts(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, filters.start_date, filters.end_date]);

  if (!open) return null;

  const allCats = CATEGORY_GROUPS.flatMap((g) => g.categories);
  const allSelected = allCats.every((c) => local.includes(c));

  const toggle = (cat: string) =>
    setLocal((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );

  const toggleAll = () => {
    if (allSelected) {
      setLocal([]);
    } else {
      setLocal([...allCats]);
    }
  };

  const handleProceduralToggle = () => {
    const next = !includeProcedural;
    setIncludeProcedural(next);
    if (next) {
      setLocal((prev) =>
        prev.includes(PROCEDURAL_CATEGORY) ? prev : [...prev, PROCEDURAL_CATEGORY]
      );
    } else {
      setLocal((prev) => prev.filter((c) => c !== PROCEDURAL_CATEGORY));
    }
  };

  const handleApply = () => {
    onApply(local);
    onClose();
  };

  const lowerSearch = search.toLowerCase();

  // Helper to find count for a category (case-insensitive match)
  const getCount = (cat: string): number | undefined => {
    if (counts[cat] !== undefined) return counts[cat];
    const lower = cat.toLowerCase();
    for (const [key, val] of Object.entries(counts)) {
      if (key.toLowerCase() === lower) return val;
    }
    return undefined;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh]">
      <div className="fixed inset-0 bg-black/20" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-[620px] mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Category</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Search */}
        <div className="px-6 pt-4 pb-2">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search categories..."
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 text-gray-900 rounded-lg text-sm placeholder-gray-400 outline-none focus:border-gray-400"
            />
          </div>
        </div>

        {/* Select all + Procedural toggle */}
        <div className="px-6 py-2 flex items-center justify-between">
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-900">
              Select All Categories
            </span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-xs text-gray-500">Show Procedural</span>
            <button
              onClick={handleProceduralToggle}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                includeProcedural ? "bg-blue-600" : "bg-gray-200"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  includeProcedural ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </label>
        </div>

        {/* Groups */}
        <div className="flex-1 overflow-y-auto px-6 pb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-6">
            {CATEGORY_GROUPS.map((group) => {
              const filtered = group.categories.filter((c) =>
                c.toLowerCase().includes(lowerSearch)
              );
              if (filtered.length === 0) return null;
              return (
                <div key={group.title}>
                  <h3 className="text-sm font-semibold text-gray-900 mb-2.5">
                    {group.title}
                  </h3>
                  <div className="space-y-2">
                    {filtered.map((cat) => {
                      const count = getCount(cat);
                      return (
                        <label
                          key={cat}
                          className="flex items-center gap-2.5 cursor-pointer group"
                        >
                          <input
                            type="checkbox"
                            checked={local.includes(cat)}
                            onChange={() => toggle(cat)}
                            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700 group-hover:text-gray-900 flex items-center gap-2">
                            {cat}
                            {count !== undefined && count > 0 && (
                              <span className="inline-flex items-center justify-center min-w-[28px] px-1.5 py-0.5 rounded-full bg-gray-100 text-[10px] font-semibold text-gray-600">
                                {count.toLocaleString()}
                              </span>
                            )}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-end">
          <button
            onClick={handleApply}
            className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
