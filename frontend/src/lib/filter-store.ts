import { create } from "zustand";
import { format } from "date-fns";
import type { FilingsParams } from "@/lib/api";

function todayStr() {
  return format(new Date(), "yyyy-MM-dd");
}

interface FilterState {
  filters: FilingsParams;
  selectedCategories: string[];
  selectedSentiments: string[];
  selectedCompanies: string[];
  selectedWatchlistId: string | null; // null = "All", a UUID = specific watchlist
  watchlistOnly: boolean;

  setFilters: (f: FilingsParams) => void;
  setSelectedCategories: (cats: string[]) => void;
  setSelectedSentiments: (sents: string[]) => void;
  setSelectedCompanies: (companies: string[]) => void;
  setSelectedWatchlistId: (id: string | null) => void;
  setWatchlistOnly: (v: boolean) => void;
  resetAll: () => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  filters: { start_date: todayStr(), end_date: todayStr() },
  selectedCategories: [],
  selectedSentiments: [],
  selectedCompanies: [],
  selectedWatchlistId: null,
  watchlistOnly: false,

  setFilters: (f) => set({ filters: f }),
  setSelectedCategories: (cats) => set({ selectedCategories: cats }),
  setSelectedSentiments: (sents) => set({ selectedSentiments: sents }),
  setSelectedCompanies: (companies) => set({ selectedCompanies: companies }),
  setSelectedWatchlistId: (id) => set({ selectedWatchlistId: id }),
  setWatchlistOnly: (v) => set({ watchlistOnly: v }),
  resetAll: () =>
    set({
      filters: { start_date: todayStr(), end_date: todayStr() },
      selectedCategories: [],
      selectedSentiments: [],
      selectedCompanies: [],
      selectedWatchlistId: null,
      watchlistOnly: false,
    }),
}));
