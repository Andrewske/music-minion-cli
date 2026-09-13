import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { CHIP_KEYS, type ChipKey } from '../components/artists/ArtistStatChip';

export type ArtistSource = 'all' | 'soundcloud' | 'local' | 'following';
export type ArtistSort =
  | 'name'
  | 'rank'
  | 'library'
  | 'reposts'
  | 'hit_rate'
  | 'noise'
  | 'last_loved';

interface ArtistViewState {
  hiddenChips: ChipKey[];
  search: string;
  source: ArtistSource;
  sort: ArtistSort;
  toggleChip: (key: ChipKey) => void;
  showAll: () => void;
  setSearch: (search: string) => void;
  setSource: (source: ArtistSource) => void;
  setSort: (sort: ArtistSort) => void;
}

// Search/source/sort live here (not route state) so they survive navigating
// to an artist page and back. source/sort also persist across reloads;
// search is intentionally session-only.
export const useArtistViewStore = create<ArtistViewState>()(
  persist(
    (set) => ({
      hiddenChips: [],
      search: '',
      source: 'all',
      sort: 'name',
      toggleChip: (key) =>
        set((state) => ({
          hiddenChips: state.hiddenChips.includes(key)
            ? state.hiddenChips.filter((k) => k !== key)
            : [...state.hiddenChips, key],
        })),
      showAll: () => set({ hiddenChips: [] }),
      setSearch: (search) => set({ search }),
      setSource: (source) => set({ source }),
      setSort: (sort) => set({ sort }),
    }),
    {
      name: 'artist-view-chips',
      partialize: (state) => ({
        hiddenChips: state.hiddenChips,
        source: state.source,
        sort: state.sort,
      }),
    },
  ),
);

export function useVisibleChips(): Set<ChipKey> {
  const hidden = useArtistViewStore((s) => s.hiddenChips);
  return new Set(CHIP_KEYS.filter((k) => !hidden.includes(k)));
}
