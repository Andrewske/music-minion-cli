import { describe, expect, it, vi } from 'vitest';
import { commitThenReplace, createTransitionLock, sessionToSync } from './sessionTransition';

describe('sessionToSync', () => {
  it('syncs to a newly loaded session of this playlist', () => {
    expect(sessionToSync({ id: 'b', playlist_id: 1 }, 'a', 1)).toBe('b');
  });

  it('does nothing when the route already matches', () => {
    expect(sessionToSync({ id: 'a', playlist_id: 1 }, 'a', 1)).toBeNull();
  });

  it('ignores a session that belongs to another playlist (late result after navigating away)', () => {
    expect(sessionToSync({ id: 'a2', playlist_id: 1 }, 'b1', 2)).toBeNull();
  });

  it('does nothing while no session is loaded', () => {
    expect(sessionToSync(undefined, 'a', 1)).toBeNull();
  });
});

describe('createTransitionLock', () => {
  it('lets only one transition in until released', () => {
    const lock = createTransitionLock();
    expect(lock.tryAcquire()).toBe(true);
    expect(lock.isHeld()).toBe(true);
    expect(lock.tryAcquire()).toBe(false);
    lock.release();
    expect(lock.isHeld()).toBe(false);
    expect(lock.tryAcquire()).toBe(true);
  });

  it('keeps locks independent', () => {
    const a = createTransitionLock();
    const b = createTransitionLock();
    a.tryAcquire();
    expect(b.tryAcquire()).toBe(true);
  });
});

describe('commitThenReplace', () => {
  it('returns the replacement and skips recovery on success', async () => {
    const onLost = vi.fn(async (): Promise<void> => undefined);
    const result = await commitThenReplace(async () => undefined, async () => 'fresh', onLost);
    expect(result).toBe('fresh');
    expect(onLost).not.toHaveBeenCalled();
  });

  it('recovers, then rethrows, when the replacement fails after a committed change', async () => {
    const calls: string[] = [];
    const run = commitThenReplace(
      async () => void calls.push('commit'),
      async (): Promise<string> => {
        calls.push('load');
        throw new Error('offline');
      },
      async () => void calls.push('lost')
    );
    await expect(run).rejects.toThrow('offline');
    expect(calls).toEqual(['commit', 'load', 'lost']);
  });

  it('does not recover when the commit itself fails (nothing changed server-side)', async () => {
    const onLost = vi.fn(async (): Promise<void> => undefined);
    const load = vi.fn(async (): Promise<string> => 'fresh');
    const run = commitThenReplace(async () => Promise.reject(new Error('500')), load, onLost);
    await expect(run).rejects.toThrow('500');
    expect(load).not.toHaveBeenCalled();
    expect(onLost).not.toHaveBeenCalled();
  });
});
