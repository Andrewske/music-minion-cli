import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as bucketsApi from '../api/buckets';
import type { BucketSession, SessionSummary } from '../api/buckets';
import { organizerSessionKey, organizerSessionsKey, usePlaylistOrganizer } from './usePlaylistOrganizer';

vi.mock('../api/buckets', () => ({
  createOrResumeSession: vi.fn(),
  listSessions: vi.fn(),
  createNewSession: vi.fn(),
  activateSession: vi.fn(),
  renameSession: vi.fn(),
  discardSession: vi.fn(),
  finalizeSession: vi.fn(),
  linkBucket: vi.fn(),
  pullLinkedTracks: vi.fn(),
  assignTrack: vi.fn(),
}));

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void; reject: (error: Error) => void } {
  let resolve: (value: T) => void = () => undefined;
  let reject: (error: Error) => void = () => undefined;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const api = vi.mocked(bucketsApi);
const PLAYLIST = 7;

function makeSession(id: string, overrides: Partial<BucketSession> = {}): BucketSession {
  return {
    id, playlist_id: PLAYLIST, status: 'active', name: null,
    created_at: '2026-11-10 12:00:00', buckets: [], unassigned_track_ids: [1, 2], ...overrides,
  };
}

const summary: SessionSummary = {
  id: 's1', playlist_id: PLAYLIST, name: null, status: 'active', created_at: '2026-11-10 12:00:00',
  last_opened_at: '2026-11-10 12:00:00', bucket_count: 0, assigned_count: 0,
};

type HookResult = { current: ReturnType<typeof usePlaylistOrganizer> };

async function setup(): Promise<{ client: QueryClient; result: HookResult }> {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  client.setQueryData(organizerSessionsKey(PLAYLIST), [summary]);
  const wrapper = ({ children }: { children: ReactNode }): JSX.Element => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => usePlaylistOrganizer({ playlistId: PLAYLIST }), { wrapper });
  await waitFor(() => expect(result.current.session?.id).toBe('s1'));
  return { client, result };
}

const listInvalidated = (client: QueryClient): boolean =>
  client.getQueryState(organizerSessionsKey(PLAYLIST))?.isInvalidated ?? false;

describe('usePlaylistOrganizer sessions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.createOrResumeSession.mockResolvedValue(makeSession('s1'));
  });

  it('switchSession writes the activated session into the loaded key without refetching', async () => {
    api.activateSession.mockResolvedValue(makeSession('s2', { name: 'Old split' }));
    const { client, result } = await setup();

    await act(async () => { await result.current.switchSession('s2'); });

    expect(api.activateSession).toHaveBeenCalledWith('s2');
    await waitFor(() => expect(result.current.session?.id).toBe('s2'));
    expect(client.getQueryData<BucketSession>(organizerSessionKey(PLAYLIST))?.name).toBe('Old split');
    expect(api.createOrResumeSession).toHaveBeenCalledTimes(1);
    expect(listInvalidated(client)).toBe(true);
  });

  it('newSession loads the fresh session and passes the optional name', async () => {
    api.createNewSession.mockResolvedValue(makeSession('s3', { unassigned_track_ids: [1, 2, 3] }));
    const { client, result } = await setup();

    await act(async () => { await result.current.newSession('Vibes'); });

    expect(api.createNewSession).toHaveBeenCalledWith(PLAYLIST, 'Vibes');
    await waitFor(() => expect(result.current.session?.id).toBe('s3'));
    expect(result.current.unassignedTrackIds).toEqual([1, 2, 3]);
    expect(listInvalidated(client)).toBe(true);
  });

  it('deleting the loaded session refetches get-or-create', async () => {
    api.discardSession.mockResolvedValue(undefined);
    const { result } = await setup();
    api.createOrResumeSession.mockResolvedValue(makeSession('s4'));

    await act(async () => { await result.current.deleteSession('s1'); });

    await waitFor(() => expect(result.current.session?.id).toBe('s4'));
    expect(api.discardSession).toHaveBeenCalledWith('s1');
  });

  it('deleting another session leaves the loaded one alone', async () => {
    api.discardSession.mockResolvedValue(undefined);
    const { client, result } = await setup();

    await act(async () => { await result.current.deleteSession('s9'); });

    expect(api.createOrResumeSession).toHaveBeenCalledTimes(1);
    expect(result.current.session?.id).toBe('s1');
    expect(listInvalidated(client)).toBe(true);
  });

  it('renameSession patches the loaded session name in place', async () => {
    api.renameSession.mockResolvedValue(undefined);
    const { result } = await setup();

    await act(async () => { await result.current.renameSession('s1', 'Dubstep split'); });

    expect(api.renameSession).toHaveBeenCalledWith('s1', 'Dubstep split');
    await waitFor(() => expect(result.current.session?.name).toBe('Dubstep split'));
  });

  it('finalizeSession loads the replacement session and refreshes the list', async () => {
    api.finalizeSession.mockResolvedValue(undefined);
    const { client, result } = await setup();
    api.createOrResumeSession.mockResolvedValue(makeSession('s5'));

    let next: BucketSession | undefined;
    await act(async () => { next = await result.current.finalizeSession(); });

    expect(api.finalizeSession).toHaveBeenCalledWith('s1');
    expect(next?.id).toBe('s5');
    await waitFor(() => expect(result.current.session?.id).toBe('s5'));
    expect(listInvalidated(client)).toBe(true);
  });

  it('a refetch that started before a switch cannot overwrite the switched-to session', async () => {
    const { client, result } = await setup();
    const stale = deferred<BucketSession>();
    api.createOrResumeSession.mockReturnValue(stale.promise);
    api.activateSession.mockResolvedValue(makeSession('s2'));

    // e.g. the onSettled invalidation of an assign, still in flight
    act(() => { void client.invalidateQueries({ queryKey: organizerSessionKey(PLAYLIST) }); });
    await waitFor(() => expect(api.createOrResumeSession).toHaveBeenCalledTimes(2));

    await act(async () => { await result.current.switchSession('s2'); });
    await act(async () => { stale.resolve(makeSession('s1')); await stale.promise; });

    await waitFor(() => expect(result.current.session?.id).toBe('s2'));
    expect(client.getQueryData<BucketSession>(organizerSessionKey(PLAYLIST))?.id).toBe('s2');
  });

  it('a failed optimistic assign does not roll back onto a session switched to meanwhile', async () => {
    const { client, result } = await setup();
    const assign = deferred<void>();
    api.assignTrack.mockReturnValue(assign.promise);
    api.activateSession.mockResolvedValue(makeSession('s2', { unassigned_track_ids: [9] }));
    // keep any post-settle refetch from changing the answer
    api.createOrResumeSession.mockReturnValue(new Promise<BucketSession>(() => undefined));

    let assignDone: Promise<void> = Promise.resolve();
    act(() => { assignDone = result.current.assignTrack('b1', 1).catch(() => undefined); });
    await waitFor(() => expect(api.assignTrack).toHaveBeenCalled());
    await act(async () => { await result.current.switchSession('s2'); });
    await act(async () => { assign.reject(new Error('boom')); await assignDone; });

    expect(client.getQueryData<BucketSession>(organizerSessionKey(PLAYLIST))?.id).toBe('s2');
  });

  it('linkBucket returns the pullable track ids to the caller', async () => {
    api.linkBucket.mockResolvedValue({ linked: true, pullable_track_ids: [4, 5] });
    const { result } = await setup();

    let pullable: number[] = [];
    await act(async () => { pullable = (await result.current.linkBucket('b1', 42)).pullable_track_ids; });

    expect(api.linkBucket).toHaveBeenCalledWith('b1', 42);
    expect(pullable).toEqual([4, 5]);
  });
});
