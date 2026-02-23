"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { X, Search } from "lucide-react";
import { searchCompanies } from "@/lib/api";
import type { Company } from "@/lib/api";

interface Props {
  open: boolean;
  selectedSymbols: string[];
  onApply: (symbols: string[]) => void;
  onClose: () => void;
}

export function CompanyFilterModal({
  open,
  selectedSymbols,
  onApply,
  onClose,
}: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Company[]>([]);
  const [local, setLocal] = useState<string[]>(selectedSymbols);
  const [searching, setSearching] = useState(false);

  useMemo(() => {
    if (open) {
      setLocal(selectedSymbols);
      setQuery("");
      setResults([]);
    }
  }, [open, selectedSymbols]);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await searchCompanies(q, 20);
      setResults(res.companies ?? []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(timer);
  }, [query, doSearch]);

  if (!open) return null;

  const toggleSymbol = (symbol: string) => {
    setLocal((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh]">
      <div className="fixed inset-0 bg-black/20" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-[480px] max-h-[70vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Company</h2>
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
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by company..."
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 text-gray-900 rounded-lg text-sm placeholder-gray-400 outline-none focus:border-gray-400"
            />
          </div>
        </div>

        {/* Selected chips */}
        {local.length > 0 && (
          <div className="px-6 py-2 flex flex-wrap gap-1.5">
            {local.map((sym) => (
              <span
                key={sym}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium"
              >
                {sym}
                <button
                  onClick={() => toggleSymbol(sym)}
                  className="hover:text-blue-900"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-6 pb-4">
          {searching && (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!searching && query.length < 2 && local.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              No companies selected.
            </p>
          )}

          {!searching && query.length >= 2 && results.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              No results found
            </p>
          )}

          {!searching &&
            results.map((c, i) => (
              <button
                key={`${c.isin}-${i}`}
                onClick={() => toggleSymbol(c.newnsecode || c.newname)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition flex items-center justify-between ${
                  local.includes(c.newnsecode || c.newname)
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <div>
                  <p className="font-medium">{c.newname}</p>
                  <p className="text-xs text-gray-400">
                    {c.newnsecode}
                    {c.isin && ` · ${c.isin}`}
                  </p>
                </div>
                {local.includes(c.newnsecode || c.newname) && (
                  <span className="text-blue-600 text-xs font-medium">
                    Selected
                  </span>
                )}
              </button>
            ))}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-between">
          {local.length > 0 && (
            <button
              onClick={() => setLocal([])}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Clear all
            </button>
          )}
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 font-medium transition"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                onApply(local);
                onClose();
              }}
              className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition"
            >
              Apply
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
