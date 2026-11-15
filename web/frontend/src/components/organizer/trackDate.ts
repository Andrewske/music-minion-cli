/**
 * Parse a track date from the backend. Two shapes arrive, both UTC:
 * SoundCloud's `2026/09/13 04:35:14 +0000` and SQLite's `2026-05-07 16:00:02`,
 * which has no offset and would otherwise parse as browser-local time.
 */
export function parseTrackDate(dateStr: string | undefined): Date | null {
  if (!dateStr) return null;
  const iso = dateStr.trim().replace(/\//g, '-').replace(' +0000', 'Z').replace(' ', 'T');
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(iso.includes('T') && !hasZone ? `${iso}Z` : iso);
  return isNaN(date.getTime()) ? null : date;
}
