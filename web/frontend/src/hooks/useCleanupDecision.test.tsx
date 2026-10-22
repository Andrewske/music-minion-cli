import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'sonner';
import type { CleanupDecisionResponse, PendingCleanupResponse } from '../api/cleanup';
import { decideCleanup } from '../api/cleanup';
import { makePage } from '../components/cleanup/cleanupTestRows';
import { CLEANUP_COUNT_KEY, CLEANUP_PENDING_KEY } from '../components/cleanup/cleanupView';
import { useCleanupDecision } from './useCleanupDecision';

vi.mock('../api/cleanup', () => ({ decideCleanup: vi.fn(), getPendingCleanup: vi.fn() }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const decideMock = vi.mocked(decideCleanup);

function setup(): { client: QueryClient; result: { current: ReturnType<typeof useCleanupDecision> } } {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  client.setQueryData(CLEANUP_PENDING_KEY, makePage('a', 'b', 'c'));
  client.setQueryData(CLEANUP_COUNT_KEY, { count: 3 });
  // Keep the invalidation refetch from replacing the optimistic list.
  client.setQueryDefaults(CLEANUP_PENDING_KEY, { queryFn: () => new Promise<PendingCleanupResponse>(() => undefined) });
  const wrapper = ({ children }: { children: ReactNode }): JSX.Element => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { result } = renderHook(() => useCleanupDecision(), { wrapper });
  return { client, result };
}

const ids = (client: QueryClient): string[] =>
  client.getQueryData<PendingCleanupResponse>(CLEANUP_PENDING_KEY)?.rows.map((row) => row.id) ?? [];

describe('useCleanupDecision', () => {
  beforeEach(() => {
    decideMock.mockReset();
    vi.mocked(toast.error).mockReset();
  });

  it('removes the row before the server answers and updates the badge after', async () => {
    let resolve: (value: CleanupDecisionResponse) => void = () => undefined;
    decideMock.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { client, result } = setup();

    act(() => result.current.mutate({ id: 'b', verdict: 'model' }));
    await waitFor(() => expect(ids(client)).toEqual(['a', 'c']));
    expect(decideMock.mock.calls[0][0]).toEqual({ id: 'b', verdict: 'model' });

    await act(async () => resolve({ id: 'b', status: 'applied', written: true, verdict: 'model', db_refreshed: true, track_id: 7, remaining: 2 }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getQueryData(CLEANUP_COUNT_KEY)).toEqual({ count: 2 });
  });

  it('puts the row back where it was and toasts the track id on error', async () => {
    decideMock.mockRejectedValue(new Error('Tag write failed'));
    const { client, result } = setup();

    act(() => result.current.mutate({ id: 'b', verdict: 'edited', expected: { title: 'X', credited_artists: [], remixers: [] } }));

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(ids(client)).toEqual(['a', 'b', 'c']);
    expect(toast.error).toHaveBeenCalledWith('Could not save b: Tag write failed');
  });

  it('moves an unclear row to the end instead of removing it', async () => {
    decideMock.mockResolvedValue({ id: 'a', status: 'pending', written: false, verdict: 'unclear', db_refreshed: false, track_id: null, remaining: 3 });
    const { client, result } = setup();

    act(() => result.current.mutate({ id: 'a', verdict: 'unclear' }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(ids(client)).toEqual(['b', 'c', 'a']);
    expect(client.getQueryData(CLEANUP_COUNT_KEY)).toEqual({ count: 3 });
  });
});
