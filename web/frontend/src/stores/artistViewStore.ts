import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { CHIP_KEYS, type ChipKey } from '../components/artists/ArtistStatChip';

interface ArtistViewState {
  hiddenChips: ChipKey[];
  toggleChip: (key: ChipKey) => void;
  showAll: () => void;
}

export const useArtistViewStore = create<ArtistViewState>()(
  persist(
    (set) => ({
      hiddenChips: [],
      toggleChip: (key) =>
        set((state) => ({
          hiddenChips: state.hiddenChips.includes(key)
            ? state.hiddenChips.filter((k) => k !== key)
            : [...state.hiddenChips, key],
        })),
      showAll: () => set({ hiddenChips: [] }),
    }),
    { name: 'artist-view-chips' },
  ),
);

export function useVisibleChips(): Set<ChipKey> {
  const hidden = useArtistViewStore((s) => s.hiddenChips);
  return new Set(CHIP_KEYS.filter((k) => !hidden.includes(k)));
}
