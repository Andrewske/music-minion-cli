import { describe, expect, it } from 'vitest';
import { upcomingStart } from '@music-minion/shared';
import type { Track } from '@music-minion/shared';
import { queueInfoLabel, upNextSlice } from './upNext';

const queue: Track[] = Array.from({ length: 15 }, (_, i) => ({ id: i + 100, title: `T${i + 1}` }));

describe('upNextSlice', () => {
  it('returns the tracks after the current index with 1-based positions', () => {
    const { rows, remaining } = upNextSlice(queue, 3, 3);
    expect(rows.map((r) => [r.track.id, r.position])).toEqual([[103, 4], [104, 5], [105, 6]]);
    expect(remaining).toBe(9);
  });

  it('caps at the default limit of 10', () => {
    const { rows, remaining } = upNextSlice(queue, 1);
    expect(rows).toHaveLength(10);
    expect(remaining).toBe(4);
  });

  it('is empty on the last track', () => {
    expect(upNextSlice(queue, 15)).toEqual({ rows: [], remaining: 0 });
  });

  it('starts at the top for a negative index', () => {
    expect(upNextSlice(queue, -2, 1).rows[0]?.position).toBe(1);
  });

  it('handles an empty queue and a zero limit', () => {
    expect(upNextSlice([], 1)).toEqual({ rows: [], remaining: 0 });
    expect(upNextSlice(queue, 1, 0)).toEqual({ rows: [], remaining: 14 });
  });
});

describe('upNextSlice with a displaced current track', () => {
  it('lists the cursor track itself when the current one left the queue', () => {
    // Organizer: A (playing) was assigned away, B inserted: queue [B] at index 0.
    const queueB: Track[] = [{ id: 2, title: 'B' }];
    const start = upcomingStart({ queue: queueB, queueIndex: 0, currentTrack: { id: 1, title: 'A' } });
    expect(upNextSlice(queueB, start).rows.map((r) => [r.track.id, r.position])).toEqual([[2, 1]]);
  });
});

describe('queueInfoLabel', () => {
  it('formats the position Maestro parses', () => {
    expect(queueInfoLabel(2, 40)).toBe('3 / 40 in queue');
  });
});
