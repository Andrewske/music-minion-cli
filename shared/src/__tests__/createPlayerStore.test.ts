import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createPlayerStore, getCurrentPosition } from '../stores/createPlayerStore.js';
import { createMemoryStorageAdapter } from '../stores/storage.js';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const makeDeps = () => ({
  storage: createMemoryStorageAdapter(),
  apiBase: 'http://test:8642/api',
  getDeviceName: () => 'Test Device',
  generateDeviceId: () => 'test-device-123',
});

describe('createPlayerStore', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('creates a store with initial state', () => {
    const store = createPlayerStore(makeDeps());
    const state = store.getState();

    expect(state.currentTrack).toBeNull();
    expect(state.isPlaying).toBe(false);
    expect(state.thisDeviceId).toBe('test-device-123');
    expect(state.thisDeviceName).toBe('Test Device');
    expect(state.queue).toEqual([]);
  });

  it('reads initial volume from storage', () => {
    const deps = makeDeps();
    deps.storage.setItem('music-minion-volume', '0.75');
    const store = createPlayerStore(deps);
    expect(store.getState().volume).toBe(0.75);
  });

  it('reads initial shuffle from storage', () => {
    const deps = makeDeps();
    deps.storage.setItem('music-minion-shuffle', 'false');
    const store = createPlayerStore(deps);
    expect(store.getState().shuffleEnabled).toBe(false);
  });

  it('persists volume changes to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().setVolume(0.5);
    expect(deps.storage.getItem('music-minion-volume')).toBe('0.5');
    expect(store.getState().volume).toBe(0.5);
  });

  it('persists mute state to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().setMuted(true);
    expect(deps.storage.getItem('music-minion-player-muted')).toBe('true');
    expect(store.getState().isMuted).toBe(true);
  });

  it('renames device and persists to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().renameDevice('My Phone');
    expect(store.getState().thisDeviceName).toBe('My Phone');
    expect(deps.storage.getItem('music-minion-device-name')).toBe('My Phone');
  });
});

describe('syncState', () => {
  it('passes through queue-only updates', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const queue = [track, { id: 2, title: 'Song 2', artist: 'Artist' }];

    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 1000,
      trackStartedAt: Date.now() - 1000,
      queue,
      queueIndex: 0,
      serverTime: Date.now(),
    } as any);

    expect(store.getState().queueIndex).toBe(0);

    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 1000,
      trackStartedAt: Date.now() - 1000,
      queue,
      queueIndex: 1,
      serverTime: Date.now(),
    } as any);

    expect(store.getState().queueIndex).toBe(1);
  });
});

describe('getCurrentPosition', () => {
  it('returns positionMs when not playing', () => {
    const state = {
      isPlaying: false,
      trackStartedAt: null,
      positionMs: 5000,
      clockOffset: 0,
    } as any;
    expect(getCurrentPosition(state)).toBe(5000);
  });

  it('computes position from clock when playing', () => {
    const now = Date.now();
    const state = {
      isPlaying: true,
      trackStartedAt: now - 2000,
      positionMs: 1000,
      clockOffset: 0,
    } as any;
    const pos = getCurrentPosition(state);
    // Should be approximately 3000 (1000 + 2000 elapsed)
    expect(pos).toBeGreaterThanOrEqual(2900);
    expect(pos).toBeLessThanOrEqual(3100);
  });
});

describe('syncState clock offset (seconds vs milliseconds regression)', () => {
  it('preserves correct position after queue-change re-sync', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const now = Date.now();

    // Initial sync — simulates backend sending ms timestamps (post-fix)
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: now - 30_000,
      queue: [track, { id: 2, title: 'Song 2', artist: 'Artist' }],
      queueIndex: 0,
      serverTime: now,
      shuffleEnabled: true,
    } as any);

    const posAfterInitial = getCurrentPosition(store.getState());
    expect(posAfterInitial).toBeGreaterThanOrEqual(29_000);
    expect(posAfterInitial).toBeLessThanOrEqual(31_000);

    // Re-sync with changed queue (bucket assignment removes a track)
    // serverTime advances slightly, trackStartedAt unchanged — both in ms
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: now - 30_000,
      queue: [track],
      queueIndex: 0,
      serverTime: now + 50,
      shuffleEnabled: true,
    } as any);

    const posAfterResync = getCurrentPosition(store.getState());
    // Position must stay ~30s, not drop to ~30ms
    expect(posAfterResync).toBeGreaterThanOrEqual(29_000);
    expect(posAfterResync).toBeLessThanOrEqual(31_500);
  });

  it('would produce wrong position if timestamps were in seconds', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const nowSeconds = Date.now() / 1000;

    // Simulate pre-fix backend: seconds instead of ms
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: nowSeconds - 30,
      queue: [track],
      queueIndex: 0,
      serverTime: nowSeconds,
      shuffleEnabled: true,
    } as any);

    const pos = getCurrentPosition(store.getState());
    // With seconds, position would be ~30ms not ~30000ms — clearly broken
    expect(pos).toBeLessThan(1000);
  });
});
