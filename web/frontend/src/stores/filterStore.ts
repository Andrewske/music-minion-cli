import { create } from 'zustand';
import type { Filter } from '../api/builder';

interface FilterState {
  filters: Filter[];
  setFilters: (filters: Filter[]) => void;
  addFilter: (filter: Filter) => void;
  removeFilter: (index: number) => void;
  updateFilter: (index: number, filter: Filter) => void;
  clearFilters: () => void;
  toggleConjunction: (index: number) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  filters: [],
  setFilters: (filters) => set({ filters }),
  addFilter: (filter) => set((state) => ({
    filters: [...state.filters, filter]
  })),
  removeFilter: (index) => set((state) => ({
    filters: state.filters.filter((_, i) => i !== index)
  })),
  updateFilter: (index, filter) => set((state) => ({
    filters: state.filters.map((f, i) => i === index ? filter : f)
  })),
  clearFilters: () => set({ filters: [] }),
  toggleConjunction: (index) => set((state) => ({
    filters: state.filters.map((f, i) =>
      i === index
        ? { ...f, conjunction: f.conjunction === 'AND' ? 'OR' as const : 'AND' as const }
        : f
    )
  })),
}));
