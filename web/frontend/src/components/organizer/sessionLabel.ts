import type { BucketSessionStatus } from '../../api/buckets';

interface LabelledSession {
  name: string | null;
  created_at: string;
}

/**
 * Parse a backend timestamp. SQLite CURRENT_TIMESTAMP is UTC with no zone
 * ("2026-11-10 12:00:00"), so treat zone-less values as UTC.
 */
export function parseSessionDate(value: string): Date | null {
  const iso = value.includes('T') ? value : value.replace(' ', 'T');
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(hasZone ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Display name: the user's name, else "Session · Nov 10" from created_at. */
export function sessionLabel(session: LabelledSession): string {
  const trimmed = session.name?.trim();
  if (trimmed) return trimmed;
  const date = parseSessionDate(session.created_at);
  if (!date) return 'Session';
  return `Session · ${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
}

export function isDoneStatus(status: BucketSessionStatus): boolean {
  return status === 'applied';
}
