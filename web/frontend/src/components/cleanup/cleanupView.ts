import type { CleanupField, CleanupRow, CleanupVerdict, CleanupView, PendingCleanupResponse } from '../../api/cleanup';

export const CLEANUP_QUERY_KEY = ['cleanup'] as const;
export const CLEANUP_PENDING_KEY = ['cleanup', 'pending'] as const;
export const CLEANUP_COUNT_KEY = ['cleanup', 'count'] as const;
export const CLEANUP_DECISION_MUTATION_KEY = ['cleanup', 'decision'] as const;

export type CleanupSource = 'current' | 'a' | 'b';

export interface CleanupFieldSpec {
  key: CleanupField;
  label: string;
  list: boolean;
}

export const CLEANUP_FIELDS: readonly CleanupFieldSpec[] = [
  { key: 'title', label: 'Title', list: false },
  { key: 'credited_artists', label: 'Artists', list: true },
  { key: 'remixers', label: 'Remixers', list: true },
];

export const CLEANUP_SOURCES: readonly { key: CleanupSource; label: string }[] = [
  { key: 'current', label: 'Current' },
  { key: 'a', label: 'Run A' },
  { key: 'b', label: 'Run B' },
];

/** One highlighted piece of a cell: a name (lists) or a word (titles). */
export interface DiffToken {
  text: string;
  changed: boolean;
}

/** Same rule as review.html: names in lists are joined with "; ". */
export function toText(value: string | string[]): string {
  return Array.isArray(value) ? value.join('; ') : value;
}

export function namesFromText(text: string): string[] {
  return text.split(';').map((part) => part.trim()).filter(Boolean);
}

const words = (text: string): string[] => text.split(/\s+/).filter(Boolean);

export function sameValue(left: string | string[], right: string | string[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

/**
 * Tokens of `value` marked changed when absent from `base`: list fields
 * compare whole names, titles compare words. Exact match, so a casing fix
 * shows up as a change.
 */
export function diffTokens(value: string | string[], base: string | string[]): DiffToken[] {
  const tokens = Array.isArray(value) ? value : words(value);
  const baseline = new Set(Array.isArray(base) ? base : words(base));
  return tokens.map((text) => ({ text, changed: !baseline.has(text) }));
}

/** Highlight per cell: the current column is the baseline; A/B are compared to it. */
export function cellTokens(row: CleanupRow, field: CleanupField, source: CleanupSource): DiffToken[] {
  const value = row[source][field];
  return diffTokens(value, source === 'current' ? value : row.current[field]);
}

/** Title words: merge runs with the same flag so a changed phrase is one highlight. */
export function groupWords(tokens: DiffToken[]): DiffToken[] {
  return tokens.reduce<DiffToken[]>((groups, token) => {
    const last = groups[groups.length - 1];
    if (last && last.changed === token.changed) {
      return [...groups.slice(0, -1), { ...last, text: `${last.text} ${token.text}` }];
    }
    return [...groups, token];
  }, []);
}

export function cellChanged(row: CleanupRow, field: CleanupField, source: CleanupSource): boolean {
  return source !== 'current' && !sameValue(row[source][field], row.current[field]);
}

/** True when runs A and B disagree on this field (exact compare). */
export function runsDisagree(row: CleanupRow, field: CleanupField): boolean {
  return !sameValue(row.a[field], row.b[field]);
}

export function viewFromDraft(draft: Record<CleanupField, string>): CleanupView {
  return {
    title: draft.title.trim(),
    credited_artists: namesFromText(draft.credited_artists),
    remixers: namesFromText(draft.remixers),
  };
}

export function draftFromView(view: CleanupView): Record<CleanupField, string> {
  return {
    title: view.title,
    credited_artists: toText(view.credited_artists),
    remixers: toText(view.remixers),
  };
}

export interface OptimisticDecision {
  data: PendingCleanupResponse;
  /** The row as it was and where, so an error can put it back. */
  removed: { row: CleanupRow; index: number } | null;
}

/** Unclear rows move to the end (still pending); every other verdict removes the row. */
export function applyOptimisticDecision(data: PendingCleanupResponse, id: string, verdict: CleanupVerdict): OptimisticDecision {
  const index = data.rows.findIndex((row) => row.id === id);
  if (index < 0) return { data, removed: null };
  const row = data.rows[index];
  const rest = data.rows.filter((item) => item.id !== id);
  if (verdict === 'unclear') {
    return { data: { ...data, rows: [...rest, { ...row, unclear: true }] }, removed: { row, index } };
  }
  return { data: { rows: rest, count: Math.max(0, data.count - 1) }, removed: { row, index } };
}

/** Put a row back after a failed decision, unless a refetch already has it. */
export function rollbackDecision(data: PendingCleanupResponse, removed: { row: CleanupRow; index: number }): PendingCleanupResponse {
  const without = data.rows.filter((row) => row.id !== removed.row.id);
  const wasRemoved = without.length === data.rows.length;
  const rows = [...without.slice(0, removed.index), removed.row, ...without.slice(removed.index)];
  return { rows, count: wasRemoved ? data.count + 1 : data.count };
}
