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

/** Compact age for the organizer Date column: `<1d`, `3d`, `2w`, `5mo`, `1y`. */
export function formatRelativeDate(dateStr: string | undefined): string {
  const date = parseTrackDate(dateStr);
  if (!date) return '-';
  const days = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (days < 1) return '<1d';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  if (days < 365) return `${Math.floor(days / 30)}mo`;
  return `${Math.floor(days / 365)}y`;
}

export function formatFullDate(dateStr: string | undefined): string {
  const date = parseTrackDate(dateStr);
  return date ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
}
