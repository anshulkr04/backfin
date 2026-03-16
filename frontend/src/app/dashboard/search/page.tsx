"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { searchCompanies, getCorporateFilings } from "@/lib/api";
import type { Company, Filing } from "@/lib/api";
import { Search as SearchIcon, Building2, ArrowLeft } from "lucide-react";
import { AnnouncementDetail } from "@/components/announcement-detail-new";

export default function SearchPage() {
  const { token } = useAuth();
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [searching, setSearching] = useState(false);
  const [companyFilings, setCompanyFilings] = useState<Filing[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [loadingFilings, setLoadingFilings] = useState(false);
  const [selectedFiling, setSelectedFiling] = useState<Filing | null>(null);

  const doSearch = useCallback(
    async (q: string) => {
      if (!token || q.length < 2) {
        setCompanies([]);
        return;
      }
      setSearching(true);
      try {
        const res = await searchCompanies(q);
        setCompanies(res.companies ?? []);
      } catch {
        setCompanies([]);
      } finally {
        setSearching(false);
      }
    },
    [token]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setQuery(v);
    // debounce would be nicer; simple approach
    doSearch(v);
  };

  const selectCompany = async (c: Company) => {
    if (!token) return;
    setSelectedCompany(c);
    setSelectedFiling(null);
    setLoadingFilings(true);
    try {
      const res = await getCorporateFilings({ symbol: c.newnsecode });
      setCompanyFilings(res.filings ?? []);
    } catch {
      setCompanyFilings([]);
    } finally {
      setLoadingFilings(false);
    }
  };

  // Show filing detail
  if (selectedFiling) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <button
            onClick={() => setSelectedFiling(null)}
            className="text-gray-500 hover:text-gray-900 transition"
          >
            <ArrowLeft size={18} />
          </button>
          <span className="text-sm font-medium text-gray-900">
            Back to {selectedCompany?.newname ?? "Results"}
          </span>
        </div>
        <div className="flex-1 overflow-hidden">
          <AnnouncementDetail filing={selectedFiling} />
        </div>
      </div>
    );
  }

  // Show company filings
  if (selectedCompany) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-6 py-5 border-b border-gray-100">
          <button
            onClick={() => {
              setSelectedCompany(null);
              setCompanyFilings([]);
            }}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-900 transition mb-3"
          >
            <ArrowLeft size={14} />
            Back to search
          </button>
          <h1 className="text-lg font-bold text-gray-900">
            {selectedCompany.newname}
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {selectedCompany.newnsecode}{" "}
            {selectedCompany.isin && `· ${selectedCompany.isin}`}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingFilings ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : companyFilings.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-20">
              No filings found for this company
            </p>
          ) : (
            <div className="divide-y divide-gray-50">
              {companyFilings.map((f, idx) => (
                <button
                  key={`${f.corp_id}-${idx}`}
                  onClick={() => setSelectedFiling(f)}
                  className="w-full text-left px-6 py-4 hover:bg-gray-50 transition"
                >
                  <p className="text-sm font-medium text-gray-900 line-clamp-2">
                    {f.headline || f.summary}
                  </p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-xs text-gray-400">{f.date}</span>
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      {f.category}
                    </span>
                    {f.sentiment && (
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          f.sentiment === "Positive"
                            ? "bg-green-50 text-green-700"
                            : f.sentiment === "Negative"
                            ? "bg-red-50 text-red-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {f.sentiment}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Default search view
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-5 border-b border-gray-100">
        <h1 className="text-lg font-bold text-gray-900 mb-4">
          Search Companies
        </h1>
        <div className="relative">
          <SearchIcon
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            value={query}
            onChange={handleChange}
            placeholder="Search by company name, symbol, or ISIN..."
            className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-100 transition"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {searching && (
          <div className="flex items-center justify-center py-10">
            <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!searching && query.length < 2 && (
          <div className="flex flex-col items-center justify-center py-20 text-sm text-gray-400">
            <SearchIcon size={32} className="mb-3 text-gray-300" />
            <p>Type at least 2 characters to search</p>
          </div>
        )}

        {!searching && query.length >= 2 && companies.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-20">
            No companies found
          </p>
        )}

        {!searching && companies.length > 0 && (
          <div className="divide-y divide-gray-50">
            {companies.map((c, i) => (
              <button
                key={i}
                onClick={() => selectCompany(c)}
                className="w-full text-left px-6 py-4 hover:bg-gray-50 transition flex items-center gap-3"
              >
                <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                  <Building2 size={16} className="text-gray-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {c.newname}
                  </p>
                  <p className="text-xs text-gray-400">
                    {c.newnsecode}
                    {c.isin && ` · ${c.isin}`}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
