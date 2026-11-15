import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createPlayerStore, upcomingStart, withScLiked } from '../stores/createPlayerStore.js';
import type { SyncStatePayload, Track } from '../stores/createPlayerStore.js';
import { createMemoryStorageAdapter } from '../stores/storage.js';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const API = 'http://test:8642/api';
type Store = ReturnType<typeof createPlayerStore>;

const track = (id: number, scId: string | null = null): Track => ({
  id,
  title: `Track ${id}`,
  soundcloud_id: scId,
  sc_liked: false,
});

const payload = (overrides: Partial<SyncStatePayload> = {}): SyncStatePayload => {
  const queue = [track(1, '101'), track(2), track(3, '103')];
  return {
    currentTrack: queue[0] ?? null,
    queue,
    queueIndex: 0,
    isPlaying: true,
    activeDeviceId: 'dev-1',
    positionMs: 5_000,
    trackStartedAt: Date.now() - 1_000,
    shuffleEnabled: false,
    serverTime: Date.now(),
    queueVersion: 1,
    stateSeq: 1,
    ...overrides,
  };
};

const seed = (overrides: Partial<SyncStatePayload> = {}): Store => {
  const store = createPlayerStore({
    storage: createMemoryStorageAdapter(),
    apiBase: API,
    getDeviceName: () => 'Test',
    generateDeviceId: () => 'dev-1',
  });
  store.getState().syncState(payload(overrides));
  return store;
};

const ok = (body: unknown): Response => new Response(JSON.stringify(body), { status: 200 });
const fail = (status: number, detail: string): Response =>
  new Response(JSON.stringify({ detail }), { status });

const lastCall = (): [string, RequestInit] => {
  const call = mockFetch.mock.calls.at(-1);
  if (!call) throw new Error('fetch was not called');
  return [String(call[0]), call[1] as RequestInit];
};

beforeEach(() => {
  mockFetch.mockReset();
});

describe('withScLiked', () => {
  it('patches every copy of the SoundCloud track and nothing else', () => {
    const t1 = track(1, '101');
    const out = withScLiked({ currentTrack: t1, queue: [t1, track(2)] }, '101', true);
    expect(out.currentTrack?.sc_liked).toBe(true);
    expect(out.queue.map((t) => t.sc_liked)).toEqual([true, false]);
  });
});

describe('queueTrack', () => {
  it('POSTs the track and position', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(ok({ index: 1, queue_size: 4 }));
    await store.getState().queueTrack(track(9), 'next');
    const [url, init] = lastCall();
    expect(url).toBe(`${API}/player/queue`);
    expect(JSON.parse(String(init.body))).toEqual({ trackId: 9, position: 'next' });
  });

  it('throws the server detail', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(fail(400, 'Nothing is playing; start playback first'));
    await expect(store.getState().queueTrack(track(9), 'last')).rejects.toThrow('Nothing is playing');
  });
});

describe('jumpTo', () => {
  it('moves the cursor optimistically and sends index + trackId', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(ok({ queue_index: 2 }));
    const pending = store.getState().jumpTo(2);
    expect(store.getState().queueIndex).toBe(2);
    expect(store.getState().currentTrack?.id).toBe(3);
    expect(store.getState().positionMs).toBe(0);
    await pending;
    expect(JSON.parse(String(lastCall()[1].body))).toEqual({ index: 2, trackId: 3 });
  });

  it('rolls back and reports a stale-queue conflict', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(fail(409, 'Queue changed'));
    await store.getState().jumpTo(1);
    expect(store.getState().queueIndex).toBe(0);
    expect(store.getState().currentTrack?.id).toBe(1);
    expect(store.getState().playbackError).toBe('Queue changed');
  });

  it('ignores the current index and out-of-range taps', async () => {
    const store = seed();
    await store.getState().jumpTo(0);
    await store.getState().jumpTo(10);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe('displaced current track (organizer queue emptied, B inserted)', () => {
  const displaced = (): Partial<SyncStatePayload> => ({
    currentTrack: track(1, '101'),
    queue: [track(2)],
    queueIndex: 0,
  });

  it('upcomingStart is the cursor itself', () => {
    expect(upcomingStart({ queue: [track(2)], queueIndex: 0, currentTrack: track(1) })).toBe(0);
    expect(upcomingStart({ queue: [track(1), track(2)], queueIndex: 0, currentTrack: track(1) })).toBe(1);
  });

  it('jumpTo(0) plays B instead of returning early', async () => {
    const store = seed(displaced());
    mockFetch.mockResolvedValueOnce(ok({ queue_index: 0 }));
    await store.getState().jumpTo(0);
    expect(store.getState().currentTrack?.id).toBe(2);
    expect(JSON.parse(String(lastCall()[1].body))).toEqual({ index: 0, trackId: 2 });
  });

  it('optimistic next lands on B, matching the server', () => {
    const store = seed(displaced());
    mockFetch.mockReturnValue(new Promise(() => {}));
    void store.getState().next();
    expect(store.getState().currentTrack?.id).toBe(2);
    expect(store.getState().queueIndex).toBe(0);
  });
});

describe('setLiked', () => {
  it('flips the heart before the request lands, then PUTs', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(ok({ soundcloud_id: '101', sc_liked: true }));
    const pending = store.getState().setLiked(true);
    expect(store.getState().currentTrack?.sc_liked).toBe(true);
    expect(store.getState().queue[0]?.sc_liked).toBe(true);
    await pending;
    const [url, init] = lastCall();
    expect(url).toBe(`${API}/soundcloud/likes/101`);
    expect(init.method).toBe('PUT');
  });

  it('unlike sends DELETE', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(ok({ soundcloud_id: '101', sc_liked: false }));
    await store.getState().setLiked(false);
    expect(lastCall()[1].method).toBe('DELETE');
  });

  it('rolls back and throws on failure', async () => {
    const store = seed();
    mockFetch.mockResolvedValueOnce(fail(500, 'boom'));
    await expect(store.getState().setLiked(true)).rejects.toThrow('boom');
    expect(store.getState().currentTrack?.sc_liked).toBe(false);
  });

  it('does nothing for a local-only track', async () => {
    const store = seed({ currentTrack: track(2), queueIndex: 1 });
    await store.getState().setLiked(true);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe('syncState keeps the current track object', () => {
  it('reuses it for the same track, replaces it when sc_liked changed', () => {
    const store = seed();
    const held = store.getState().currentTrack;
    store.getState().syncState(payload({ stateSeq: 2, positionMs: 9_000 }));
    expect(store.getState().currentTrack).toBe(held);

    const liked = { ...track(1, '101'), sc_liked: true };
    store.getState().syncState(payload({ stateSeq: 3, queueVersion: 2, currentTrack: liked }));
    expect(store.getState().currentTrack?.sc_liked).toBe(true);
  });

  it('applies a like whose queue fetch landed before its broadcast', () => {
    const store = seed();
    const liked = { ...track(1, '101'), sc_liked: true };
    // The queue refetch already brought version 2 (with the like) ...
    store.getState().set({ queue: [liked, track(2), track(3, '103')], queueVersion: 2 });
    // ... so the slim broadcast for version 2 matches every echo field but the heart.
    const { queue: _omit, ...slim } = payload({ stateSeq: 2, queueVersion: 2, currentTrack: liked });
    store.getState().syncState(slim);
    expect(store.getState().currentTrack?.sc_liked).toBe(true);
  });
});
