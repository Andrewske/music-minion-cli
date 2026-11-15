// Remembers the last playlist opened in the Playlist Organizer so the index
// route can resume it. Storage can throw (private mode, blocked site data),
// so every access is guarded and failure just means "nothing remembered".
const STORAGE_KEY = 'music-minion-organizer-last-playlist';

export function getLastOrganizerPlaylistId(): number | null {
  try {
    const parsed = parseInt(localStorage.getItem(STORAGE_KEY) ?? '', 10);
    return Number.isNaN(parsed) ? null : parsed;
  } catch {
    return null;
  }
}

export function setLastOrganizerPlaylistId(playlistId: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(playlistId));
  } catch {
    // Not persisting is fine; the index page falls back to the list.
  }
}
