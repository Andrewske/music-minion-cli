/**
 * Pure helpers for the organizer session switcher (labels, rows, playback binding).
 * Mirrors web/frontend/src/components/organizer/sessionLabel.ts.
 */
import type { BucketSession, BucketSessionStatus, PlayContext, SessionSummary } from '@music-minion/shared';
import type { SessionCounts } from './organizerState';

interface LabelledSession {
  name: string | null;
  created_at: string;
}

/**
 * Parse a backend timestamp. SQLite CURRENT_TIMESTAMP is UTC with no zone
 * ("2026-11-10 12:00:00"), so zone-less values are treated as UTC.
 */
export function parseSessionDate(value: string): Date | null {
  const iso = value.includes('T') ? value : value.replace(' ', 'T');
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(hasZone ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Display name: the user's name, else "Session · Nov 10" from created_at (local day). */
export function sessionLabel(session: LabelledSession): string {
  const trimmed = session.name?.trim();
  if (trimmed) return trimmed;
  const date = parseSessionDate(session.created_at);
  if (!date) return 'Session';
  // Hermes' toLocaleDateString ignores options on some builds, so format by hand.
  return `Session · ${MONTHS[date.getMonth()]} ${date.getDate()}`;
}

/** Applied (finished) sessions can be reopened but are marked "done". */
export function isDoneStatus(status: BucketSessionStatus): boolean {
  return status === 'applied';
}

/** "4 buckets · 88 sorted" */
export function sessionCountsText(summary: SessionSummary): string {
  const buckets = summary.bucket_count === 1 ? '1 bucket' : `${summary.bucket_count} buckets`;
  return `${buckets} · ${summary.assigned_count} sorted`;
}

/** Header subtitle: "Dubstep split · 12/40 sorted · 28 left". */
export function sessionSubtitle(session: LabelledSession | undefined, counts: SessionCounts): string {
  const progress = `${counts.assigned}/${counts.total} sorted · ${counts.unassigned} left`;
  return session ? `${sessionLabel(session)} · ${progress}` : progress;
}

export interface SwitcherRows {
  current: SessionSummary | undefined;
  others: SessionSummary[];
}

/** Split the list into the loaded session's summary and every other session (list order kept). */
export function splitSessions(sessions: readonly SessionSummary[], loadedId: string | undefined): SwitcherRows {
  return {
    current: sessions.find((s) => s.id === loadedId),
    others: sessions.filter((s) => s.id !== loadedId),
  };
}

/** Rename draft → value to send: blank clears the name; null when nothing changed. */
export function renameValue(draft: string, currentName: string | null): { name: string | null } | null {
  const name = draft.trim() || null;
  return name === (currentName?.trim() || null) ? null : { name };
}

/** True when live playback is organizer context bound to this session. */
export function isPlaybackBoundTo(context: PlayContext | null, sessionId: string | undefined): boolean {
  return sessionId !== undefined && context?.type === 'organizer' && context.session_id === sessionId;
}

/** True when a session change left `leavingId` for a different session that playback should follow. */
export function shouldRebindPlayback(
  context: PlayContext | null,
  leavingId: string | undefined,
  next: Pick<BucketSession, 'id'> | null
): boolean {
  if (!next || !leavingId || next.id === leavingId) return false;
  return isPlaybackBoundTo(context, leavingId);
}
