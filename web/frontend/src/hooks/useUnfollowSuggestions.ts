import { useRef, useState } from 'react';
import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import * as api from '../api/unfollowSuggestions';
import type { OkResponse } from '../api/followSuggestions';
import type {
  UnfollowAccountResponse, UnfollowBatchResponse, UnfollowCandidate, UnfollowSection, UnfollowSuggestionsResponse,
} from '../api/unfollowSuggestions';
import { findRows, reinsertRows, SUGGESTIONS_KEY } from './useFollowSuggestions';
import type { RemovedRow } from './useFollowSuggestions';

export const UNFOLLOW_KEY = ['unfollow-suggestions', 'list'] as const;
/** Shared by the row mutations, so the last one to settle refetches once. */
export const UNFOLLOW_MUTATION_KEY = ['unfollow-suggestions', 'mutation'] as const;
export const SECTIONS: readonly UnfollowSection[] = ['redundant', 'dormant', 'labels', 'low_yield'];

// ---------------------------------------------------------------------------
// Pure cache transforms
// ---------------------------------------------------------------------------

type Sections = UnfollowSuggestionsResponse['sections'];
type Rows = RemovedRow<UnfollowSection, UnfollowCandidate>[];

/** Drops rows from every section; `unfollowed` of them leave the following count. */
export function withoutCandidates(
  data: UnfollowSuggestionsResponse, ids: ReadonlySet<number>, unfollowed: number,
): UnfollowSuggestionsResponse {
  const keep = (c: UnfollowCandidate): boolean => !ids.has(c.discovery_artist_id);
  const sections = Object.fromEntries(
    SECTIONS.map((s) => [s, data.sections[s].filter(keep)]),
  ) as Sections;
  const following = { ...data.following, count: Math.max(0, data.following.count - unfollowed) };
  return { ...data, sections, following };
}

/** Puts rows back where they were and restores `unfollowed` to the count. */
export function withCandidatesBack(
  data: UnfollowSuggestionsResponse, rows: Rows, unfollowed: number,
): UnfollowSuggestionsResponse {
  const same = (a: UnfollowCandidate, b: UnfollowCandidate): boolean => a.discovery_artist_id === b.discovery_artist_id;
  const sections = reinsertRows(data.sections, rows, same);
  return { ...data, sections, following: { ...data.following, count: data.following.count + unfollowed } };
}

/** [[1..25], [26..50], ...] */
export function chunk<T>(items: readonly T[], size: number): T[][] {
  return Array.from({ length: Math.ceil(items.length / size) }, (_, i) => items.slice(i * size, (i + 1) * size));
}

const succeeded = (res: UnfollowBatchResponse): number[] => res.results.filter((r) => r.ok).map((r) => r.id);

// ---------------------------------------------------------------------------
// Optimistic helpers
// ---------------------------------------------------------------------------

interface Removal {
  rows: Rows;
  unfollowed: number;
}

async function removeOptimistically(client: QueryClient, id: number, unfollowed: number): Promise<Removal> {
  await client.cancelQueries({ queryKey: UNFOLLOW_KEY });
  const data = client.getQueryData<UnfollowSuggestionsResponse>(UNFOLLOW_KEY);
  if (!data) return { rows: [], unfollowed: 0 };
  client.setQueryData(UNFOLLOW_KEY, withoutCandidates(data, new Set([id]), unfollowed));
  return { rows: findRows(data.sections, SECTIONS, (c) => c.discovery_artist_id === id), unfollowed };
}

function undoRemoval(client: QueryClient, removal: Removal | undefined): void {
  if (!removal || removal.rows.length === 0) return;
  client.setQueryData<UnfollowSuggestionsResponse>(UNFOLLOW_KEY, (current) =>
    current && withCandidatesBack(current, removal.rows, removal.unfollowed));
}

/** Once nothing is in flight, the server state wins (and the follow page's meter too). */
function refetchWhenIdle(client: QueryClient): void {
  if (client.isMutating({ mutationKey: UNFOLLOW_MUTATION_KEY }) > 1) return;
  for (const queryKey of [UNFOLLOW_KEY, SUGGESTIONS_KEY, ['artists', 'list']]) {
    void client.invalidateQueries({ queryKey });
  }
}

const errorText = (err: unknown, fallback: string): string => (err instanceof Error ? err.message : fallback);

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useUnfollowSuggestions(): UseQueryResult<UnfollowSuggestionsResponse> {
  return useQuery({ queryKey: UNFOLLOW_KEY, queryFn: api.getUnfollowSuggestions, staleTime: 5 * 60 * 1000 });
}

/** Accounts with a keep or unfollow in flight; their buttons wait. */
export function usePendingUnfollowIds(): ReadonlySet<number> {
  const ids = useMutationState({
    filters: { mutationKey: UNFOLLOW_MUTATION_KEY, status: 'pending' },
    select: (m) => m.state.variables,
  });
  return new Set(ids.filter((id): id is number => typeof id === 'number'));
}

export function useUnfollowCandidate(): UseMutationResult<UnfollowAccountResponse, Error, number, Removal> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: UNFOLLOW_MUTATION_KEY,
    mutationFn: api.unfollowSuggested,
    onMutate: (id) => removeOptimistically(client, id, 1),
    onError: (err, _id, removal) => {
      undoRemoval(client, removal);
      toast.error(errorText(err, 'Unfollow failed'));
    },
    onSettled: () => refetchWhenIdle(client),
  });
}

export function useKeepFollowing(): UseMutationResult<OkResponse, Error, number, Removal> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: UNFOLLOW_MUTATION_KEY,
    mutationFn: api.keepFollowing,
    onMutate: (id) => removeOptimistically(client, id, 0),
    onError: (err, _id, removal) => {
      undoRemoval(client, removal);
      toast.error(errorText(err, 'Keep failed'));
    },
    onSettled: () => refetchWhenIdle(client),
  });
}

export interface BulkProgress {
  done: number;
  failed: number;
  total: number;
}

export interface BulkUnfollow {
  /** Null when no bulk run is going. */
  progress: BulkProgress | null;
  stopping: boolean;
  run: (ids: number[]) => Promise<void>;
  /** Finishes the batch in flight, then stops. */
  stop: () => void;
}

/** Applies one batch's successes to the cache; returns how many failed. */
function applyBatch(client: QueryClient, res: UnfollowBatchResponse): number {
  const ok = succeeded(res);
  client.setQueryData<UnfollowSuggestionsResponse>(UNFOLLOW_KEY, (current) =>
    current && withoutCandidates(current, new Set(ok), ok.length));
  return res.results.length - ok.length;
}

function reportBulk(progress: BulkProgress, error: string | null): void {
  if (error) toast.error(`Stopped after ${progress.done} unfollows: ${error}`);
  else if (progress.failed > 0) toast.error(`${progress.failed} unfollows failed`);
  else toast.success(`Unfollowed ${progress.done}`);
}

/** Unfollows a whole section in server batches of 25; rows go as they succeed. */
export function useBulkUnfollow(): BulkUnfollow {
  const client = useQueryClient();
  const [progress, setProgress] = useState<BulkProgress | null>(null);
  const [stopping, setStopping] = useState(false);
  const stopRef = useRef(false);
  const run = async (ids: number[]): Promise<void> => {
    stopRef.current = false;
    await client.cancelQueries({ queryKey: UNFOLLOW_KEY });
    const final = await runBatches(client, ids, () => stopRef.current, setProgress);
    reportBulk(final.progress, final.error);
    setProgress(null);
    setStopping(false);
    refetchWhenIdle(client);
  };
  const stop = (): void => {
    stopRef.current = true;
    setStopping(true);
  };
  return { progress, stopping, run, stop };
}

async function runBatches(
  client: QueryClient, ids: number[], stopped: () => boolean, onProgress: (p: BulkProgress) => void,
): Promise<{ progress: BulkProgress; error: string | null }> {
  let progress: BulkProgress = { done: 0, failed: 0, total: ids.length };
  onProgress(progress);
  for (const batch of chunk(ids, api.UNFOLLOW_BATCH_SIZE)) {
    if (stopped()) break;
    const res = await api.unfollowBatch(batch).catch((err: unknown) => errorText(err, 'Unfollow failed'));
    if (typeof res === 'string') return { progress, error: res };
    const failed = applyBatch(client, res);
    progress = { ...progress, done: progress.done + res.results.length - failed, failed: progress.failed + failed };
    onProgress(progress);
    if (res.stopped) return { progress, error: res.error };
  }
  return { progress, error: null };
}
