import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import * as api from '../api/followSuggestions';
import type {
  FollowAccountResponse, FollowConnection, FollowConnectionsResponse, FollowSuggestionsResponse,
  LinkSuggestionResponse, OkResponse, Suggestion, UntieredResponse,
} from '../api/followSuggestions';
import { updateArtist } from '../api/artists';
import type { ArtistTier, UpdateArtistResult } from '../api/artists';

export const SUGGESTIONS_KEY = ['follow-suggestions', 'list'] as const;
export const CONNECTIONS_KEY = ['follow-suggestions', 'connections'] as const;
export const UNTIERED_KEY = ['follow-suggestions', 'untiered'] as const;
/** Shared by every mutation below, so the last one to settle refetches once. */
export const FOLLOW_MUTATION_KEY = ['follow-suggestions', 'mutation'] as const;

// ---------------------------------------------------------------------------
// Pure cache transforms
// ---------------------------------------------------------------------------

type Account = Pick<Suggestion, 'key' | 'soundcloud_user_id'>;

/** Matches by key, or by SC id so a follow from one list clears the other lists too. */
const isAccount = (key: string) => (a: Account): boolean =>
  a.key === key || (a.soundcloud_user_id != null && a.soundcloud_user_id === key);

export function withoutSuggestion(data: FollowSuggestionsResponse, key: string): FollowSuggestionsResponse {
  const keep = (a: Suggestion): boolean => !isAccount(key)(a);
  return { ...data, artists: data.artists.filter(keep), labels: data.labels.filter(keep) };
}

export function withoutConnection(data: FollowConnectionsResponse, key: string): FollowConnectionsResponse {
  const keep = (a: FollowConnection): boolean => !isAccount(key)(a);
  return { co_credit: data.co_credit.filter(keep), favorites_follow: data.favorites_follow.filter(keep) };
}

/** Moves a suggestion between the artists and labels lists. */
export function withLabel(data: FollowSuggestionsResponse, key: string, isLabel: boolean): FollowSuggestionsResponse {
  const moved = [...data.artists, ...data.labels]
    .filter((a) => a.key === key)
    .map((a) => ({ ...a, is_label: isLabel }));
  const rest = withoutSuggestion(data, key);
  return isLabel
    ? { ...rest, labels: [...moved, ...rest.labels] }
    : { ...rest, artists: [...moved, ...rest.artists] };
}

export function withoutUntiered(data: UntieredResponse, id: number): UntieredResponse {
  return {
    recent: data.recent.filter((a) => a.discovery_artist_id !== id),
    rated: data.rated.filter((a) => a.discovery_artist_id !== id),
  };
}

type Lists<L extends string, I> = { [K in L]: I[] };

/** One row taken out of a cached list, and where it was. */
export interface RemovedRow<L extends string, I> {
  list: L;
  index: number;
  item: I;
}

export function findRows<L extends string, I>(
  data: Lists<L, I>, lists: readonly L[], match: (item: I) => boolean,
): RemovedRow<L, I>[] {
  return lists.flatMap((list) => data[list].flatMap((item, index) => (match(item) ? [{ list, index, item }] : [])));
}

/**
 * Puts rows back at their old positions in the current data, skipping any
 * already there. Only these rows change, so other mutations' edits survive.
 * `exclusive` names lists a row may only be in one of (artists / labels):
 * a row present in any of them counts as already there.
 */
export function reinsertRows<L extends string, I, D extends Lists<L, I>>(
  data: D, rows: readonly RemovedRow<L, I>[], same: (a: I, b: I) => boolean, exclusive: readonly L[] = [],
): D {
  return rows.reduce<D>((acc, row) => {
    const lists = exclusive.includes(row.list) ? exclusive : [row.list];
    if (lists.some((l) => acc[l].some((x) => same(x, row.item)))) return acc;
    const list = acc[row.list];
    return { ...acc, [row.list]: [...list.slice(0, row.index), row.item, ...list.slice(row.index)] };
  }, data);
}

// ---------------------------------------------------------------------------
// Optimistic helpers
// ---------------------------------------------------------------------------

type SuggestionList = 'artists' | 'labels';
type ConnectionList = 'co_credit' | 'favorites_follow';
type UntieredRow = UntieredResponse['recent'][number];

const SUGGESTION_LISTS: readonly SuggestionList[] = ['artists', 'labels'];
const CONNECTION_LISTS: readonly ConnectionList[] = ['co_credit', 'favorites_follow'];
const UNTIERED_LISTS: readonly ('recent' | 'rated')[] = ['recent', 'rated'];

const sameKey = (a: Account, b: Account): boolean => a.key === b.key;
const sameArtist = (a: UntieredRow, b: UntieredRow): boolean => a.discovery_artist_id === b.discovery_artist_id;

/** What one mutation took out of the caches, to put back if it fails. */
interface Removal {
  suggestions: RemovedRow<SuggestionList, Suggestion>[];
  connections: RemovedRow<ConnectionList, FollowConnection>[];
}

async function removeAccountOptimistically(client: QueryClient, key: string): Promise<Removal> {
  await client.cancelQueries({ queryKey: ['follow-suggestions'] });
  const suggestions = client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY);
  const connections = client.getQueryData<FollowConnectionsResponse>(CONNECTIONS_KEY);
  if (suggestions) client.setQueryData(SUGGESTIONS_KEY, withoutSuggestion(suggestions, key));
  if (connections) client.setQueryData(CONNECTIONS_KEY, withoutConnection(connections, key));
  return {
    suggestions: suggestions ? findRows(suggestions, SUGGESTION_LISTS, isAccount(key)) : [],
    connections: connections ? findRows(connections, CONNECTION_LISTS, isAccount(key)) : [],
  };
}

/** Re-inserts only this mutation's rows into whatever the caches hold now. */
function undoRemoval(client: QueryClient, removal: Removal | undefined): void {
  if (!removal) return;
  client.setQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY, (current) =>
    current && reinsertRows(current, removal.suggestions, sameKey, SUGGESTION_LISTS));
  client.setQueryData<FollowConnectionsResponse>(CONNECTIONS_KEY, (current) =>
    current && reinsertRows(current, removal.connections, sameKey));
}

/** The account a follow / dismiss / label mutation acts on (tier changes: null). */
export function mutationAccountKey(variables: unknown): string | null {
  if (typeof variables === 'string') return variables;
  if (variables && typeof variables === 'object' && 'key' in variables) {
    const { key } = variables as { key: unknown };
    return typeof key === 'string' ? key : null;
  }
  return null;
}

/**
 * True when a mutation on the same account started after the one that owns
 * `context` and has not failed. Its optimistic edit (or success) is newer,
 * so rolling this one back would resurrect or duplicate the row; the
 * refetch once everything settles puts the server state in place instead.
 */
function supersededByLater(client: QueryClient, context: unknown, key: string): boolean {
  const all = client.getMutationCache().findAll({ mutationKey: FOLLOW_MUTATION_KEY });
  const mine = all.find((m) => m.state.context === context);
  if (!mine) return false;
  return all.some((m) => m.mutationId > mine.mutationId
    && m.state.status !== 'error'
    && mutationAccountKey(m.state.variables) === key);
}

/** Once the last follow-suggestion mutation settles, the server state wins. */
function refetchWhenIdle(client: QueryClient): void {
  if (client.isMutating({ mutationKey: FOLLOW_MUTATION_KEY }) > 1) return;
  for (const queryKey of [SUGGESTIONS_KEY, CONNECTIONS_KEY, UNTIERED_KEY]) {
    void client.invalidateQueries({ queryKey });
  }
}

const errorText = (err: unknown, fallback: string): string => (err instanceof Error ? err.message : fallback);

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useFollowSuggestions(): UseQueryResult<FollowSuggestionsResponse> {
  return useQuery({ queryKey: SUGGESTIONS_KEY, queryFn: api.getFollowSuggestions, staleTime: 5 * 60 * 1000 });
}

/** No retries: the section hides itself quietly when the endpoint fails. */
export function useFollowConnections(): UseQueryResult<FollowConnectionsResponse> {
  return useQuery({ queryKey: CONNECTIONS_KEY, queryFn: api.getFollowConnections, staleTime: 5 * 60 * 1000, retry: false });
}

export function useUntieredFollows(): UseQueryResult<UntieredResponse> {
  return useQuery({ queryKey: UNTIERED_KEY, queryFn: api.getUntieredFollows, staleTime: 60 * 1000 });
}

/** Accounts with a follow, dismiss or label change in flight; their rows wait. */
export function usePendingAccountKeys(): ReadonlySet<string> {
  const keys = useMutationState({
    filters: { mutationKey: FOLLOW_MUTATION_KEY, status: 'pending' },
    select: (m) => mutationAccountKey(m.state.variables),
  });
  return new Set(keys.filter((k): k is string => k != null));
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

export function useFollowAccount(): UseMutationResult<FollowAccountResponse, Error, string, Removal> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: FOLLOW_MUTATION_KEY,
    mutationFn: api.followAccount,
    onMutate: (id) => removeAccountOptimistically(client, id),
    onError: (err, id, removal) => {
      if (!supersededByLater(client, removal, id)) undoRemoval(client, removal);
      toast.error(errorText(err, 'Follow failed'));
    },
    onSuccess: () => {
      // The new follow lands in the untiered list at tier C.
      void client.invalidateQueries({ queryKey: UNTIERED_KEY });
      void client.invalidateQueries({ queryKey: ['artists', 'list'] });
    },
    onSettled: () => refetchWhenIdle(client),
  });
}

export function useDismissSuggestion(): UseMutationResult<OkResponse, Error, string, Removal> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: FOLLOW_MUTATION_KEY,
    mutationFn: api.dismissSuggestion,
    onMutate: (key) => removeAccountOptimistically(client, key),
    onError: (err, key, removal) => {
      if (!supersededByLater(client, removal, key)) undoRemoval(client, removal);
      toast.error(errorText(err, 'Dismiss failed'));
    },
    onSettled: () => refetchWhenIdle(client),
  });
}

interface LabelVars {
  key: string;
  isLabel: boolean;
}

type LabelRows = RemovedRow<SuggestionList, Suggestion>[];

/** Takes the moved row out of its new list and puts the original back. */
function undoLabel(client: QueryClient, key: string, rows: LabelRows | undefined): void {
  if (!rows) return;
  client.setQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY, (current) => {
    if (!current) return current;
    const notMoved = (a: Suggestion): boolean => a.key !== key;
    const without = { ...current, artists: current.artists.filter(notMoved), labels: current.labels.filter(notMoved) };
    return reinsertRows(without, rows, sameKey, SUGGESTION_LISTS);
  });
}

export function useSetSuggestionLabel(): UseMutationResult<OkResponse, Error, LabelVars, LabelRows> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: FOLLOW_MUTATION_KEY,
    mutationFn: ({ key, isLabel }: LabelVars) => api.setSuggestionLabel(key, isLabel),
    onMutate: async ({ key, isLabel }) => {
      await client.cancelQueries({ queryKey: SUGGESTIONS_KEY });
      const suggestions = client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY);
      if (!suggestions) return [];
      client.setQueryData(SUGGESTIONS_KEY, withLabel(suggestions, key, isLabel));
      return findRows(suggestions, SUGGESTION_LISTS, (a) => a.key === key);
    },
    onError: (err, { key }, rows) => {
      if (!supersededByLater(client, rows, key)) undoLabel(client, key, rows);
      toast.error(errorText(err, 'Label update failed'));
    },
    onSettled: () => refetchWhenIdle(client),
  });
}

interface LinkVars {
  key: string;
  url: string;
}

/** No optimistic edit: the row merges into the linked account on refetch. */
export function useLinkSuggestion(): UseMutationResult<LinkSuggestionResponse, Error, LinkVars> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: FOLLOW_MUTATION_KEY,
    mutationFn: ({ key, url }: LinkVars) => api.linkSuggestion(key, url),
    onSuccess: (res) => toast.success(`Linked to ${res.display_name ?? res.soundcloud_user_id}`),
    onError: (err) => toast.error(errorText(err, 'Link failed')),
    onSettled: () => refetchWhenIdle(client),
  });
}

interface TierVars {
  id: number;
  tier: ArtistTier;
}

type UntieredRows = RemovedRow<'recent' | 'rated', UntieredRow>[];

export function useTierUntiered(): UseMutationResult<UpdateArtistResult, Error, TierVars, UntieredRows> {
  const client = useQueryClient();
  return useMutation({
    mutationKey: FOLLOW_MUTATION_KEY,
    mutationFn: ({ id, tier }: TierVars) => updateArtist(id, { tier }),
    onMutate: async ({ id }) => {
      await client.cancelQueries({ queryKey: UNTIERED_KEY });
      const previous = client.getQueryData<UntieredResponse>(UNTIERED_KEY);
      if (!previous) return [];
      client.setQueryData(UNTIERED_KEY, withoutUntiered(previous, id));
      return findRows(previous, UNTIERED_LISTS, (a) => a.discovery_artist_id === id);
    },
    onError: (err, _vars, rows) => {
      client.setQueryData<UntieredResponse>(UNTIERED_KEY, (current) =>
        current && reinsertRows(current, rows ?? [], sameArtist));
      toast.error(errorText(err, 'Tier update failed'));
    },
    // Tier changes renumber every artist's ranking.
    onSuccess: () => void client.invalidateQueries({ queryKey: ['artists', 'list'] }),
    onSettled: () => refetchWhenIdle(client),
  });
}
