/**
 * Organizer store — remembers the session the user last opened so the picker
 * can offer a "Resume" entry. In-memory only; the server keeps the session
 * itself, so losing this on app restart just hides the shortcut.
 */
import { create } from 'zustand';

export interface ActiveOrganizerSession {
  sessionId: string;
  playlistId: number;
  playlistName: string;
}

interface OrganizerState {
  activeSession: ActiveOrganizerSession | null;
  setActiveSession: (session: ActiveOrganizerSession) => void;
  clearActiveSession: () => void;
}

export const useOrganizerStore = create<OrganizerState>()((set) => ({
  activeSession: null,
  setActiveSession: (session: ActiveOrganizerSession): void => set({ activeSession: session }),
  clearActiveSession: (): void => set({ activeSession: null }),
}));
