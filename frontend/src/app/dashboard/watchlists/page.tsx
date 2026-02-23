"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import {
  getWatchlists,
  createWatchlist,
  deleteWatchlist,
  addIsinToWatchlist,
  removeIsinFromWatchlist,
  addCategoriesToWatchlist,
  removeCategoryFromWatchlist,
  searchCompanies,
  resolveIsins,
} from "@/lib/api";
import type { Watchlist, Company } from "@/lib/api";
import { CATEGORY_GROUPS } from "@/lib/categories";
import {
  List,
  Plus,
  Trash2,
  Search,
  X,
  Settings,
  Building2,
  Tag,
  BellOff,
  Mail,
  MessageCircle,
  ChevronRight,
} from "lucide-react";

type AlertPref = "none" | "telegram" | "email";
type EditTab = "settings" | "companies" | "categories";

export default function WatchlistsPage() {
  const { token } = useAuth();
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Create / Edit mode
  const [editing, setEditing] = useState(false);
  const [editTab, setEditTab] = useState<EditTab>("settings");
  const [editName, setEditName] = useState("");
  const [alertPref, setAlertPref] = useState<AlertPref>("none");

  // Alert preference modal on creation
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [pendingWatchlistName, setPendingWatchlistName] = useState("");

  // Company search
  const [companyQuery, setCompanyQuery] = useState("");
  const [companyResults, setCompanyResults] = useState<Company[]>([]);
  const [searchingCompany, setSearchingCompany] = useState(false);

  // Category selection
  const [categorySearch, setCategorySearch] = useState("");

  // ISIN → company name map
  const [isinNames, setIsinNames] = useState<Record<string, string>>({});

  // Delete confirmation modal
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await getWatchlists(token);
      setWatchlists(res.watchlists ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const selected = watchlists.find((w) => w._id === selectedId) ?? null;

  // Resolve ISINs to company names whenever watchlists change
  useEffect(() => {
    const allIsins = watchlists.flatMap((w) => w.isin ?? []);
    const unresolved = allIsins.filter((i) => !isinNames[i]);
    if (unresolved.length === 0) return;
    resolveIsins(unresolved).then((mapping) => {
      setIsinNames((prev) => ({ ...prev, ...mapping }));
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchlists]);

  // --- Handlers ---

  const handleStartCreate = () => {
    setPendingWatchlistName("");
    setShowAlertModal(true);
  };

  const handleConfirmCreate = async () => {
    if (!token || !pendingWatchlistName.trim()) return;
    try {
      const res = await createWatchlist(token, pendingWatchlistName.trim());
      setShowAlertModal(false);
      await fetchAll();
      setSelectedId(res.watchlist_id);
      setEditing(true);
      setEditTab("companies");
      setEditName(pendingWatchlistName.trim());
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = (id: string) => {
    setDeleteTarget(id);
  };

  const confirmDelete = async () => {
    if (!token || !deleteTarget) return;
    setDeleting(true);
    try {
      await deleteWatchlist(token, deleteTarget);
      // Optimistically remove from local state instead of full refetch
      setWatchlists((prev) => prev.filter((w) => w._id !== deleteTarget));
      if (selectedId === deleteTarget) {
        setSelectedId(null);
        setEditing(false);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const handleSelectWatchlist = (id: string) => {
    setSelectedId(id);
    setEditing(false);
    setEditTab("settings");
    const wl = watchlists.find((w) => w._id === id);
    if (wl) setEditName(wl.watchlistName);
  };

  const handleStartEdit = () => {
    if (!selected) return;
    setEditName(selected.watchlistName);
    setEditing(true);
    setEditTab("settings");
  };

  const handleAddCompany = async (company: Company) => {
    if (!token || !selectedId) return;
    try {
      await addIsinToWatchlist(token, selectedId, company.isin);
      await fetchAll();
      setCompanyQuery("");
      setCompanyResults([]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRemoveCompany = async (isin: string) => {
    if (!token || !selectedId) return;
    try {
      await removeIsinFromWatchlist(token, selectedId, isin);
      await fetchAll();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddCategory = async (category: string) => {
    if (!token || !selectedId || !selected) return;
    const currentCats = selected.categories ?? [];
    if (currentCats.includes(category)) return;
    // Optimistically update local state
    setWatchlists((prev) =>
      prev.map((w) =>
        w._id === selectedId
          ? { ...w, categories: [...(w.categories ?? []), category] }
          : w
      )
    );
    try {
      await addCategoriesToWatchlist(token, selectedId, [category]);
    } catch (err) {
      console.error(err);
      // Revert on failure
      setWatchlists((prev) =>
        prev.map((w) =>
          w._id === selectedId
            ? { ...w, categories: currentCats }
            : w
        )
      );
    }
  };

  const handleRemoveCategory = async (category: string) => {
    if (!token || !selectedId || !selected) return;
    const currentCats = selected.categories ?? [];
    // Optimistically update local state
    setWatchlists((prev) =>
      prev.map((w) =>
        w._id === selectedId
          ? { ...w, categories: (w.categories ?? []).filter((c) => c !== category) }
          : w
      )
    );
    try {
      await removeCategoryFromWatchlist(token, selectedId, category);
    } catch (err) {
      console.error(err);
      // Revert on failure
      setWatchlists((prev) =>
        prev.map((w) =>
          w._id === selectedId
            ? { ...w, categories: currentCats }
            : w
        )
      );
    }
  };

  // Company search with debounce
  useEffect(() => {
    if (companyQuery.length < 2) {
      setCompanyResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchingCompany(true);
      try {
        const res = await searchCompanies(companyQuery, 10);
        setCompanyResults(res.companies ?? []);
      } catch {
        setCompanyResults([]);
      } finally {
        setSearchingCompany(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [companyQuery]);

  return (
    <div className="flex h-full">
      {/* Left panel - Watchlist list */}
      <div className="w-[280px] shrink-0 border-r border-gray-100 flex flex-col bg-white">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900">My Watchlists</h2>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : watchlists.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-400">
              No watchlists yet
            </div>
          ) : (
            <div className="py-2">
              {watchlists.map((wl) => (
                <button
                  key={wl._id}
                  onClick={() => handleSelectWatchlist(wl._id)}
                  className={`w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-gray-50 transition ${
                    selectedId === wl._id ? "bg-gray-50" : ""
                  }`}
                >
                  <List size={16} className="text-gray-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${selectedId === wl._id ? "text-gray-900" : "text-gray-700"}`}>
                      {wl.watchlistName}
                    </p>
                    <p className="text-[11px] text-gray-400">
                      {wl.isin?.length ?? 0} Companies
                    </p>
                  </div>
                  <ChevronRight size={14} className="text-gray-300 shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleStartCreate}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 transition"
          >
            <Plus size={16} />
            Create New Watchlist
          </button>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <List size={32} className="mb-3 text-gray-300" />
            <p className="text-sm">Select a watchlist to view details</p>
          </div>
        ) : editing ? (
          /* ─── Edit / Create Mode ─── */
          <div className="flex flex-col h-full">
            <div className="px-8 py-5 border-b border-gray-100">
              <h1 className="text-xl font-bold text-gray-900">Edit Watchlist</h1>
              <div className="flex items-center gap-1 mt-3 border-b border-gray-100">
                {(["settings", "companies", "categories"] as EditTab[]).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setEditTab(tab)}
                    className={`px-4 py-2 text-sm font-medium capitalize transition border-b-2 -mb-px ${
                      editTab === tab
                        ? "border-gray-900 text-gray-900"
                        : "border-transparent text-gray-400 hover:text-gray-600"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
              {editTab === "settings" && (
                <div className="max-w-xl">
                  <div className="bg-white rounded-xl border border-gray-200 p-6">
                    <label className="text-sm font-semibold text-gray-700 mb-2 block">
                      Watchlist Name
                    </label>
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-900 outline-none focus:border-gray-400"
                      placeholder="Untitled Watchlist"
                    />

                    <h3 className="text-sm font-semibold text-gray-700 mt-6 mb-3">
                      Alert Preferences
                    </h3>
                    <div className="space-y-2">
                      {([
                        { value: "telegram" as AlertPref, label: "Instant Alerts", desc: "Receive a WhatsApp message for each important announcement as it happens.", icon: MessageCircle },
                        { value: "email" as AlertPref, label: "End of Day Summary", desc: "Get a single email digest of all announcements from the day.", icon: Mail },
                        { value: "none" as AlertPref, label: "No Alerts", desc: "You will not receive any push notifications or emails for this watchlist.", icon: BellOff },
                      ]).map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => setAlertPref(opt.value)}
                          className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition ${
                            alertPref === opt.value
                              ? "border-gray-900 bg-gray-50"
                              : "border-gray-200 hover:bg-gray-50"
                          }`}
                        >
                          <opt.icon size={20} className="text-gray-500 shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-gray-900">{opt.label}</p>
                            <p className="text-xs text-gray-400 mt-0.5">{opt.desc}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {editTab === "companies" && (
                <div>
                  {/* Search bar */}
                  <div className="relative mb-4">
                    <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      value={companyQuery}
                      onChange={(e) => setCompanyQuery(e.target.value)}
                      placeholder="Search to add a company (e.g. Reliance, HDFC Bank)"
                      className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-lg text-sm text-gray-900 outline-none focus:border-gray-400 placeholder-gray-400"
                    />
                    {companyQuery && (
                      <button
                        onClick={() => { setCompanyQuery(""); setCompanyResults([]); }}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>

                  {/* Search results dropdown */}
                  {companyQuery.length >= 2 && (
                    <div className="mb-6 border border-gray-200 rounded-lg overflow-hidden max-h-[240px] overflow-y-auto">
                      {searchingCompany ? (
                        <div className="py-4 text-center text-sm text-gray-400">Searching...</div>
                      ) : companyResults.length === 0 ? (
                        <div className="py-4 text-center text-sm text-gray-400">No companies found</div>
                      ) : (
                        companyResults.map((c) => {
                          const alreadyAdded = selected?.isin?.includes(c.isin);
                          return (
                            <button
                              key={c.isin}
                              onClick={() => !alreadyAdded && handleAddCompany(c)}
                              disabled={alreadyAdded}
                              className={`w-full flex items-center justify-between px-4 py-3 text-left border-b border-gray-50 last:border-b-0 transition ${
                                alreadyAdded ? "bg-gray-50 opacity-60" : "hover:bg-gray-50"
                              }`}
                            >
                              <div>
                                <p className="text-sm font-medium text-gray-900">{c.newname}</p>
                                <p className="text-[11px] text-gray-400 mt-0.5">
                                  {c.newnsecode && `NSE: ${c.newnsecode}`}
                                  {c.newnsecode && c.newbsecode && " · "}
                                  {c.newbsecode && `BSE: ${c.newbsecode}`}
                                  {" · "}ISIN: {c.isin}
                                </p>
                              </div>
                              {alreadyAdded ? (
                                <span className="text-[11px] text-gray-400 font-medium">Added</span>
                              ) : (
                                <Plus size={16} className="text-gray-400" />
                              )}
                            </button>
                          );
                        })
                      )}
                    </div>
                  )}

                  {/* Tracked companies list */}
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">
                    Tracked Companies ({selected?.isin?.length ?? 0})
                  </h3>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    {(selected?.isin?.length ?? 0) === 0 ? (
                      <div className="py-8 text-center text-sm text-gray-400">
                        No companies added yet.
                      </div>
                    ) : (
                      selected!.isin.map((isin) => (
                        <div
                          key={isin}
                          className="flex items-center justify-between px-4 py-3 border-b border-gray-50 last:border-b-0"
                        >
                          <div>
                            <span className="text-sm text-gray-700 font-medium">{isinNames[isin] || isin}</span>
                            {isinNames[isin] && (
                              <span className="text-[11px] text-gray-400 ml-2">{isin}</span>
                            )}
                          </div>
                          <button
                            onClick={() => handleRemoveCompany(isin)}
                            className="text-gray-300 hover:text-red-500 transition p-1"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {editTab === "categories" && (
                <div>
                  {/* Tracked categories */}
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">
                    Tracked Categories ({(selected?.categories ?? []).length})
                  </h3>
                  {(selected?.categories ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-5">
                      {(selected?.categories ?? []).map((cat) => (
                        <span
                          key={cat}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-orange-50 text-orange-700 rounded-full text-xs font-medium"
                        >
                          {cat}
                          <button
                            onClick={() => handleRemoveCategory(cat)}
                            className="hover:text-orange-900 transition"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Search */}
                  <div className="relative mb-4">
                    <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      value={categorySearch}
                      onChange={(e) => setCategorySearch(e.target.value)}
                      placeholder="Search categories..."
                      className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-lg text-sm text-gray-900 outline-none focus:border-gray-400 placeholder-gray-400"
                    />
                  </div>

                  {/* Category groups */}
                  <div className="space-y-4">
                    {CATEGORY_GROUPS.map((group) => {
                      const cats = group.categories.filter((c) =>
                        c.toLowerCase().includes(categorySearch.toLowerCase())
                      );
                      if (cats.length === 0) return null;
                      return (
                        <div key={group.title}>
                          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                            {group.title}
                          </p>
                          <div className="grid grid-cols-2 gap-1.5">
                            {cats.map((cat) => {
                              const isTracked = (selected?.categories ?? []).includes(cat);
                              return (
                                <button
                                  key={cat}
                                  onClick={() => isTracked ? handleRemoveCategory(cat) : handleAddCategory(cat)}
                                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition ${
                                    isTracked
                                      ? "bg-orange-50 text-orange-700 font-medium"
                                      : "text-gray-600 hover:bg-gray-50"
                                  }`}
                                >
                                  <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                                    isTracked ? "bg-orange-500 border-orange-500" : "border-gray-300"
                                  }`}>
                                    {isTracked && (
                                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                                        <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                      </svg>
                                    )}
                                  </div>
                                  {cat}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Bottom bar */}
            <div className="px-8 py-4 border-t border-gray-100 flex items-center justify-end gap-3">
              <button
                onClick={() => setEditing(false)}
                className="px-5 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition"
              >
                Save Changes
              </button>
            </div>
          </div>
        ) : (
          /* ─── Detail View ─── */
          <div className="flex flex-col h-full">
            <div className="px-8 py-5 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-gray-900">{selected.watchlistName}</h1>
                <button
                  onClick={handleStartEdit}
                  className="text-gray-400 hover:text-gray-600 transition"
                >
                  <Settings size={16} />
                </button>
              </div>
              <button
                onClick={handleStartEdit}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 transition flex items-center gap-2"
              >
                <Settings size={14} />
                Edit
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Tracked Companies */}
                <div className="border border-gray-200 rounded-xl">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                      <Building2 size={16} className="text-gray-400" />
                      Tracked Companies ({selected.isin?.length ?? 0})
                    </h3>
                    <button
                      onClick={() => { setEditing(true); setEditTab("companies"); }}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Edit
                    </button>
                  </div>
                  <div className="divide-y divide-gray-50">
                    {(selected.isin?.length ?? 0) === 0 ? (
                      <div className="py-8 text-center text-sm text-gray-400">
                        No companies being tracked.
                      </div>
                    ) : (
                      <>
                        {selected.isin.slice(0, 5).map((isin) => (
                          <div key={isin} className="px-5 py-3 text-sm text-gray-700">
                            <span className="font-medium">{isinNames[isin] || isin}</span>
                            {isinNames[isin] && (
                              <span className="text-[11px] text-gray-400 ml-2">{isin}</span>
                            )}
                          </div>
                        ))}
                        {selected.isin.length > 5 && (
                          <button
                            onClick={() => { setEditing(true); setEditTab("companies"); }}
                            className="w-full px-5 py-3 text-sm text-blue-600 hover:text-blue-700 font-medium text-left"
                          >
                            Show {selected.isin.length - 5} More
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Tracked Categories */}
                <div className="border border-gray-200 rounded-xl">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                      <Tag size={16} className="text-gray-400" />
                      Tracked Categories ({(selected.categories ?? []).length})
                    </h3>
                    <button
                      onClick={() => { setEditing(true); setEditTab("categories"); }}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Edit
                    </button>
                  </div>
                  <div className="p-5">
                    {(selected.categories ?? []).length === 0 ? (
                      <div className="py-4 text-center text-sm text-gray-400">
                        No categories being tracked.
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {(selected.categories ?? []).map((cat) => (
                          <span
                            key={cat}
                            className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-full font-medium"
                          >
                            {cat}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Delete button */}
              <div className="mt-8">
                <button
                  onClick={() => handleDelete(selected._id)}
                  className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600 font-medium transition"
                >
                  <Trash2 size={14} />
                  Delete Watchlist
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/20" onClick={() => setDeleteTarget(null)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-[400px] p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
                <Trash2 size={18} className="text-red-500" />
              </div>
              <div>
                <h2 className="text-base font-bold text-gray-900">Delete Watchlist</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Are you sure you want to delete this watchlist? This action cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 mt-5">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-5 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-5 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Watchlist Modal with Alert Preferences */}
      {showAlertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/20" onClick={() => setShowAlertModal(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-[500px] p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Create New Watchlist</h2>

            <label className="text-sm font-medium text-gray-700 mb-1.5 block">Watchlist Name</label>
            <input
              autoFocus
              value={pendingWatchlistName}
              onChange={(e) => setPendingWatchlistName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleConfirmCreate(); }}
              placeholder="e.g. Pharma Stocks, IT Sector..."
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-900 outline-none focus:border-gray-400 mb-5"
            />

            <h3 className="text-sm font-semibold text-gray-700 mb-3">Alert Preferences</h3>
            <div className="space-y-2 mb-6">
              {([
                { value: "telegram" as AlertPref, label: "Instant Alerts", desc: "Receive a WhatsApp message for each important announcement as it happens.", icon: MessageCircle },
                { value: "email" as AlertPref, label: "End of Day Summary", desc: "Get a single email digest of all announcements from the day.", icon: Mail },
                { value: "none" as AlertPref, label: "No Alerts", desc: "You will not receive any push notifications or emails for this watchlist.", icon: BellOff },
              ]).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setAlertPref(opt.value)}
                  className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition ${
                    alertPref === opt.value
                      ? "border-gray-900 bg-gray-50"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <opt.icon size={20} className="text-gray-500 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{opt.label}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{opt.desc}</p>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowAlertModal(false)}
                className="px-5 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmCreate}
                disabled={!pendingWatchlistName.trim()}
                className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition disabled:opacity-50"
              >
                Create Watchlist
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
