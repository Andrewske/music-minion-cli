import { create } from 'zustand';

type Library = 'local' | 'soundcloud';

interface LibraryState {
  activeLibrary: Library;
  setActiveLibrary: (library: Library) => void;
}

const getInitialLibrary = (): Library => {
  if (typeof window === 'undefined') return 'local';
  const stored = localStorage.getItem('music-minion-library');
  // Default to 'local', only accept 'soundcloud' as valid alternative
  return stored === 'soundcloud' ? 'soundcloud' : 'local';
};

export const useLibraryStore = create<LibraryState>((set) => ({
  activeLibrary: getInitialLibrary(),

  setActiveLibrary: (library) => {
    localStorage.setItem('music-minion-library', library);
    set({ activeLibrary: library });
  },
}));
