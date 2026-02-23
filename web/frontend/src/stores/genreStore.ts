import { create } from 'zustand';
import { listGenres, type GenreInfo } from '../api/genres';

interface GenreState {
  genres: GenreInfo[];
  isLoading: boolean;
  error: string | null;
}

interface GenreActions {
  fetchGenres: () => Promise<void>;
  updateGenre: (updated: GenreInfo) => void;
  removeGenre: (genreId: number) => void;
}

export const useGenreStore = create<GenreState & GenreActions>((set) => ({
  genres: [],
  isLoading: false,
  error: null,

  fetchGenres: async () => {
    set({ isLoading: true, error: null });
    try {
      const genres = await listGenres();
      set({ genres, isLoading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch genres', isLoading: false });
    }
  },

  updateGenre: (updated: GenreInfo) => {
    set((state) => ({
      genres: state.genres.map((g) => (g.id === updated.id ? updated : g)),
    }));
  },

  removeGenre: (genreId: number) => {
    set((state) => ({
      genres: state.genres.filter((g) => g.id !== genreId),
    }));
  },
}));
