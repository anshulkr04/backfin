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

  setFilters: (f: FilingsParams) => void;
  setSelectedCategories: (cats: string[]) => void;
  setSelectedSentiments: (sents: string[]) => void;
  setSelectedCompanies: (companies: string[]) => void;
  resetAll: () => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  filters: { start_date: todayStr(), end_date: todayStr() },
  selectedCategories: [],
  selectedSentiments: [],
  selectedCompanies: [],

  setFilters: (f) => set({ filters: f }),
  setSelectedCategories: (cats) => set({ selectedCategories: cats }),
  setSelectedSentiments: (sents) => set({ selectedSentiments: sents }),
  setSelectedCompanies: (companies) => set({ selectedCompanies: companies }),
  resetAll: () =>
    set({
      filters: { start_date: todayStr(), end_date: todayStr() },
      selectedCategories: [],
      selectedSentiments: [],
      selectedCompanies: [],
    }),
}));
