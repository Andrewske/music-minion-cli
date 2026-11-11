import { describe, expect, it } from 'vitest';
import { parseSessionDate, sessionLabel } from './sessionLabel';

describe('sessionLabel', () => {
  it('uses the trimmed name when set', () => {
    expect(sessionLabel({ name: '  Dubstep split ', created_at: '2026-11-03 10:00:00' })).toBe('Dubstep split');
  });

  it('falls back to the created date for null or blank names', () => {
    expect(sessionLabel({ name: null, created_at: '2026-11-10 12:00:00' })).toBe('Session · Nov 10');
    expect(sessionLabel({ name: '   ', created_at: '2026-10-20T12:00:00Z' })).toBe('Session · Oct 20');
  });

  it('survives an unparseable date', () => {
    expect(sessionLabel({ name: null, created_at: 'garbage' })).toBe('Session');
  });

  it('treats zone-less SQLite timestamps as UTC', () => {
    expect(parseSessionDate('2026-11-10 12:00:00')?.toISOString()).toBe('2026-11-10T12:00:00.000Z');
  });
});
