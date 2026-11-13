import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { dismissSuggestion, followAccount, setSuggestionLabel } from '../api/followSuggestions';
import type { FollowAccountResponse, FollowSuggestionsResponse, OkResponse } from '../api/followSuggestions';
import { updateArtist } from '../api/artists';
import type { UpdateArtistResult } from '../api/artists';
import {
  makeConnections, makeResponse, makeSuggestion, makeUntiered,
} from '../components/follow-suggestions/followSuggestionsFixtures';
import {
  CONNECTIONS_KEY, SUGGESTIONS_KEY, UNTIERED_KEY, findRows, reinsertRows, useDismissSuggestion, useFollowAccount,
  usePendingAccountKeys, useSetSuggestionLabel, useTierUntiered,
} from './useFollowSuggestions';

vi.mock('../api/followSuggestions', () => ({
  getFollowSuggestions: vi.fn(),
  getFollowConnections: vi.fn(),
  getUntieredFollows: vi.fn(),
  followAccount: vi.fn(),
  dismissSuggestion: vi.fn(),
  setSuggestionLabel: vi.fn(),
}));
vi.mock('../api/artists', () => ({ updateArtist: vi.fn() }));
vi.mock('react-toastify', () => ({ toast: { error: vi.fn(), success: vi.fn(), loading: vi.fn(() => 'toast-1'), update: vi.fn() } }));

const a = makeSuggestion({ key: '1', soundcloud_user_id: '1', display_name: 'A' });
const b = makeSuggestion({ key: '2', soundcloud_user_id: '2', display_name: 'B' });
const c = makeSuggestion({ key: '3', soundcloud_user_id: '3', display_name: 'C' });

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (err: Error) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => undefined;
  let reject: (err: Error) => void = () => undefined;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function setup(): { client: QueryClient; wrapper: (p: { children: ReactNode }) => ReactNode } {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  client.setQueryData(SUGGESTIONS_KEY, makeResponse([a, b, c]));
  client.setQueryData(CONNECTIONS_KEY, makeConnections());
  const wrapper = ({ children }: { children: ReactNode }): ReactNode => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

const artistKeys = (client: QueryClient): string[] =>
  client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY)?.artists.map((s) => s.key) ?? [];
const labelKeys = (client: QueryClient): string[] =>
  client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY)?.labels.map((s) => s.key) ?? [];

describe('row-level rollback', () => {
  beforeEach(() => vi.clearAllMocks());

  it('a failed dismiss restores only its row, not a follow that succeeded meanwhile', async () => {
    const { client, wrapper } = setup();
    const dismissCall = deferred<OkResponse>();
    vi.mocked(dismissSuggestion).mockReturnValue(dismissCall.promise);
    vi.mocked(followAccount).mockResolvedValue({ ok: true, discovery_artist_id: 9 } as FollowAccountResponse);
    const dismiss = renderHook(() => useDismissSuggestion(), { wrapper });
    const follow = renderHook(() => useFollowAccount(), { wrapper });

    act(() => dismiss.result.current.mutate('1'));
    await waitFor(() => expect(artistKeys(client)).toEqual(['2', '3']));
    await act(async () => { await follow.result.current.mutateAsync('2'); });
    expect(artistKeys(client)).toEqual(['3']);

    await act(async () => { dismissCall.reject(new Error('nope')); });
    await waitFor(() => expect(dismiss.result.current.isError).toBe(true));
    expect(artistKeys(client)).toEqual(['1', '3']); // A back in place, B stays gone
  });

  it('refetches suggestions, connections and untiered once the last mutation settles', async () => {
    const { client, wrapper } = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const dismissCall = deferred<OkResponse>();
    vi.mocked(dismissSuggestion).mockReturnValue(dismissCall.promise);
    vi.mocked(followAccount).mockResolvedValue({ ok: true, discovery_artist_id: 9 } as FollowAccountResponse);
    const dismiss = renderHook(() => useDismissSuggestion(), { wrapper });
    const follow = renderHook(() => useFollowAccount(), { wrapper });

    act(() => dismiss.result.current.mutate('1'));
    await act(async () => { await follow.result.current.mutateAsync('2'); });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: SUGGESTIONS_KEY });

    await act(async () => { dismissCall.reject(new Error('nope')); });
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: SUGGESTIONS_KEY }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: CONNECTIONS_KEY });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: UNTIERED_KEY });
  });

  it('a failed label move puts only that row back where it was', async () => {
    const { client, wrapper } = setup();
    const labelCall = deferred<OkResponse>();
    vi.mocked(setSuggestionLabel).mockReturnValue(labelCall.promise);
    vi.mocked(dismissSuggestion).mockResolvedValue({ ok: true });
    const label = renderHook(() => useSetSuggestionLabel(), { wrapper });
    const dismiss = renderHook(() => useDismissSuggestion(), { wrapper });

    act(() => label.result.current.mutate({ key: '2', isLabel: true }));
    await waitFor(() => expect(artistKeys(client)).toEqual(['1', '3']));
    await act(async () => { await dismiss.result.current.mutateAsync('3'); });

    await act(async () => { labelCall.reject(new Error('nope')); });
    await waitFor(() => expect(label.result.current.isError).toBe(true));
    const data = client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY);
    expect(data?.artists.map((s) => s.key)).toEqual(['1', '2']);
    expect(data?.labels).toEqual([]);
    expect(data?.artists[1].is_label).toBe(false);
  });

  it('a failed label move does not resurrect a row a later dismiss removed', async () => {
    const { client, wrapper } = setup();
    const labelCall = deferred<OkResponse>();
    vi.mocked(setSuggestionLabel).mockReturnValue(labelCall.promise);
    vi.mocked(dismissSuggestion).mockResolvedValue({ ok: true });
    const label = renderHook(() => useSetSuggestionLabel(), { wrapper });
    const dismiss = renderHook(() => useDismissSuggestion(), { wrapper });

    act(() => label.result.current.mutate({ key: '2', isLabel: true }));
    await waitFor(() => expect(labelKeys(client)).toEqual(['2']));
    await act(async () => { await dismiss.result.current.mutateAsync('2'); });
    await act(async () => { labelCall.reject(new Error('nope')); });
    await waitFor(() => expect(label.result.current.isError).toBe(true));

    expect(artistKeys(client)).toEqual(['1', '3']);
    expect(labelKeys(client)).toEqual([]);
  });

  it.each([
    ['label fails first', 'label', 'dismiss'],
    ['dismiss fails first', 'dismiss', 'label'],
  ] as const)('both failing (%s) leaves the account in exactly one list', async (_name, first, second) => {
    const { client, wrapper } = setup();
    const calls = { label: deferred<OkResponse>(), dismiss: deferred<OkResponse>() };
    vi.mocked(setSuggestionLabel).mockReturnValue(calls.label.promise);
    vi.mocked(dismissSuggestion).mockReturnValue(calls.dismiss.promise);
    const label = renderHook(() => useSetSuggestionLabel(), { wrapper });
    const dismiss = renderHook(() => useDismissSuggestion(), { wrapper });
    const hooks = { label, dismiss };

    act(() => label.result.current.mutate({ key: '2', isLabel: true }));
    await waitFor(() => expect(labelKeys(client)).toEqual(['2']));
    act(() => dismiss.result.current.mutate('2'));
    await waitFor(() => expect(labelKeys(client)).toEqual([]));
    for (const which of [first, second]) {
      await act(async () => { calls[which].reject(new Error('nope')); });
      await waitFor(() => expect(hooks[which].result.current.isError).toBe(true));
    }

    const all = [...artistKeys(client), ...labelKeys(client)];
    expect(all.filter((k) => k === '2')).toHaveLength(1);
  });

  it('reports accounts with a mutation in flight as pending', async () => {
    const { wrapper } = setup();
    const labelCall = deferred<OkResponse>();
    vi.mocked(setSuggestionLabel).mockReturnValue(labelCall.promise);
    const label = renderHook(() => useSetSuggestionLabel(), { wrapper });
    const pending = renderHook(() => usePendingAccountKeys(), { wrapper });

    act(() => label.result.current.mutate({ key: '2', isLabel: true }));
    await waitFor(() => expect([...pending.result.current]).toEqual(['2']));
    await act(async () => { labelCall.resolve({ ok: true }); });
    await waitFor(() => expect(pending.result.current.size).toBe(0));
  });

  it('a failed tier update restores only its untiered row', async () => {
    const { client, wrapper } = setup();
    const seven = makeUntiered();
    const eight = makeUntiered({ discovery_artist_id: 8, display_name: 'Eight' });
    client.setQueryData(UNTIERED_KEY, { recent: [], rated: [seven, eight] });
    const first = deferred<UpdateArtistResult>();
    vi.mocked(updateArtist).mockReturnValueOnce(first.promise).mockResolvedValueOnce({ id: 8, ranking: 1, tier: 'B' });
    const tier = renderHook(() => useTierUntiered(), { wrapper });
    const other = renderHook(() => useTierUntiered(), { wrapper });

    act(() => tier.result.current.mutate({ id: 7, tier: 'A' }));
    await act(async () => { await other.result.current.mutateAsync({ id: 8, tier: 'B' }); });
    await act(async () => { first.reject(new Error('nope')); });
    await waitFor(() => expect(tier.result.current.isError).toBe(true));
    expect(client.getQueryData(UNTIERED_KEY)).toEqual({ recent: [], rated: [seven] });
  });
});

describe('findRows / reinsertRows', () => {
  it('reinserts at the old index and skips rows already present', () => {
    const data = { xs: ['a', 'b', 'c', 'd'], ys: ['e'] };
    const rows = findRows(data, ['xs', 'ys'], (v) => v === 'b' || v === 'd' || v === 'e');
    const later = { xs: ['a', 'c', 'z'], ys: ['e'] };
    expect(reinsertRows(later, rows, (p, q) => p === q)).toEqual({ xs: ['a', 'b', 'c', 'd', 'z'], ys: ['e'] });
  });

  it('skips a row present in any exclusive list', () => {
    const rows = findRows({ xs: ['a'], ys: [] as string[] }, ['xs', 'ys'], (v) => v === 'a');
    const moved = { xs: [] as string[], ys: ['a'] };
    expect(reinsertRows(moved, rows, (p, q) => p === q, ['xs', 'ys'])).toEqual(moved);
    expect(reinsertRows(moved, rows, (p, q) => p === q)).toEqual({ xs: ['a'], ys: ['a'] });
  });
});
