import { describe, expect, it } from 'vitest';
import type { PlayContext, SessionSummary } from '@music-minion/shared';
import {
  isDoneStatus,
  isPlaybackBoundTo,
  parseSessionDate,
  renameValue,
  sessionCountsText,
  sessionLabel,
  sessionSubtitle,
  shouldRebindPlayback,
  splitSessions,
} from './sessionSwitcher';

function summary(id: string, overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id,
    playlist_id: 1,
    name: null,
    status: 'parked',
    created_at: '2026-11-10 12:00:00',
    last_opened_at: null,
    bucket_count: 2,
    assigned_count: 5,
    ...overrides,
  };
}

const organizerContext = (sessionId: string): PlayContext => ({ type: 'organizer', session_id: sessionId });

describe('parseSessionDate', () => {
  it('treats zone-less SQLite timestamps as UTC', () => {
    expect(parseSessionDate('2026-11-10 12:00:00')?.toISOString()).toBe('2026-11-10T12:00:00.000Z');
  });
  it('keeps an explicit zone', () => {
    expect(parseSessionDate('2026-11-10T12:00:00+02:00')?.toISOString()).toBe('2026-11-10T10:00:00.000Z');
  });
  it('returns null for garbage', () => {
    expect(parseSessionDate('not a date')).toBeNull();
  });
});

describe('sessionLabel', () => {
  it('prefers a trimmed name', () => {
    expect(sessionLabel({ name: '  Dubstep split ', created_at: '2026-11-10 12:00:00' })).toBe('Dubstep split');
  });
  it('falls back to the created day', () => {
    expect(sessionLabel({ name: '   ', created_at: '2026-11-10 12:00:00' })).toMatch(/^Session · Nov 1[01]$/);
  });
  it('falls back to a bare "Session" when the date is unreadable', () => {
    expect(sessionLabel({ name: null, created_at: '' })).toBe('Session');
  });
});

describe('isDoneStatus', () => {
  it('marks only applied sessions as done', () => {
    expect(isDoneStatus('applied')).toBe(true);
    expect(isDoneStatus('parked')).toBe(false);
    expect(isDoneStatus('active')).toBe(false);
  });
});

describe('sessionCountsText', () => {
  it('pluralizes buckets', () => {
    expect(sessionCountsText(summary('a', { bucket_count: 1, assigned_count: 3 }))).toBe('1 bucket · 3 sorted');
    expect(sessionCountsText(summary('a', { bucket_count: 0, assigned_count: 0 }))).toBe('0 buckets · 0 sorted');
  });
});

describe('sessionSubtitle', () => {
  const counts = { total: 40, assigned: 12, unassigned: 28, buckets: 3 };
  it('prefixes the session label', () => {
    expect(sessionSubtitle({ name: 'Vibes', created_at: '' }, counts)).toBe('Vibes · 12/40 sorted · 28 left');
  });
  it('shows progress alone while the session loads', () => {
    expect(sessionSubtitle(undefined, counts)).toBe('12/40 sorted · 28 left');
  });
});

describe('splitSessions', () => {
  it('separates the loaded session and keeps list order', () => {
    const rows = splitSessions([summary('a'), summary('b'), summary('c')], 'b');
    expect(rows.current?.id).toBe('b');
    expect(rows.others.map((s) => s.id)).toEqual(['a', 'c']);
  });
  it('has no current row when the loaded session is missing from the list', () => {
    const rows = splitSessions([summary('a')], undefined);
    expect(rows.current).toBeUndefined();
    expect(rows.others).toHaveLength(1);
  });
});

describe('renameValue', () => {
  it('returns the trimmed new name', () => {
    expect(renameValue('  New  ', 'Old')).toEqual({ name: 'New' });
  });
  it('clears the name on a blank draft', () => {
    expect(renameValue('   ', 'Old')).toEqual({ name: null });
  });
  it('returns null when nothing changed', () => {
    expect(renameValue('Old ', 'Old')).toBeNull();
    expect(renameValue('', null)).toBeNull();
  });
});

describe('playback binding', () => {
  it('detects organizer playback on the session', () => {
    expect(isPlaybackBoundTo(organizerContext('a'), 'a')).toBe(true);
    expect(isPlaybackBoundTo(organizerContext('a'), 'b')).toBe(false);
    expect(isPlaybackBoundTo({ type: 'playlist', playlist_id: 1 }, 'a')).toBe(false);
    expect(isPlaybackBoundTo(null, 'a')).toBe(false);
    expect(isPlaybackBoundTo(organizerContext('a'), undefined)).toBe(false);
  });
  it('rebinds only when leaving the bound session for a different one', () => {
    expect(shouldRebindPlayback(organizerContext('a'), 'a', { id: 'b' })).toBe(true);
    expect(shouldRebindPlayback(organizerContext('a'), 'a', { id: 'a' })).toBe(false);
    expect(shouldRebindPlayback(organizerContext('a'), 'a', null)).toBe(false);
    expect(shouldRebindPlayback(organizerContext('a'), undefined, { id: 'b' })).toBe(false);
    expect(shouldRebindPlayback(organizerContext('c'), 'a', { id: 'b' })).toBe(false);
  });
});
