import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import * as api from '../api/followSuggestions';
import type {
  FollowAccountResponse, FollowConnection, FollowConnectionsResponse, FollowSuggestionsResponse,
  OkResponse, Suggestion, UntieredResponse,
} from '../api/followSuggestions';
import { updateArtist } from '../api/artists';
import type { ArtistTier, UpdateArtistResult } from '../api/artists';

export const SUGGESTIONS_KEY = ['follow-suggestions', 'list'] as const;
export const CONNECTIONS_KEY = ['follow-suggestions', 'connections'] as const;
export const UNTIERED_KEY = ['follow-suggestions', 'untiered'] as const;

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

// ---------------------------------------------------------------------------
// Optimistic helpers
// ---------------------------------------------------------------------------

interface Snapshot {
  suggestions?: FollowSuggestionsResponse;
  connections?: FollowConnectionsResponse;
}

async function removeAccountOptimistically(client: QueryClient, key: string): Promise<Snapshot> {
  await client.cancelQueries({ queryKey: ['follow-suggestions'] });
  const snapshot: Snapshot = {
    suggestions: client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY),
    connections: client.getQueryData<FollowConnectionsResponse>(CONNECTIONS_KEY),
  };
  if (snapshot.suggestions) client.setQueryData(SUGGESTIONS_KEY, withoutSuggestion(snapshot.suggestions, key));
  if (snapshot.connections) client.setQueryData(CONNECTIONS_KEY, withoutConnection(snapshot.connections, key));
  return snapshot;
}

function restore(client: QueryClient, snapshot: Snapshot | undefined): void {
  if (snapshot?.suggestions) client.setQueryData(SUGGESTIONS_KEY, snapshot.suggestions);
  if (snapshot?.connections) client.setQueryData(CONNECTIONS_KEY, snapshot.connections);
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

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

export function useFollowAccount(): UseMutationResult<FollowAccountResponse, Error, string, Snapshot> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.followAccount,
    onMutate: (id) => removeAccountOptimistically(client, id),
    onError: (err, _id, snapshot) => {
      restore(client, snapshot);
      toast.error(errorText(err, 'Follow failed'));
    },
    onSuccess: () => {
      // The new follow lands in the untiered list at tier C.
      void client.invalidateQueries({ queryKey: UNTIERED_KEY });
      void client.invalidateQueries({ queryKey: ['artists', 'list'] });
    },
  });
}

export function useDismissSuggestion(): UseMutationResult<OkResponse, Error, string, Snapshot> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.dismissSuggestion,
    onMutate: (key) => removeAccountOptimistically(client, key),
    onError: (err, _key, snapshot) => {
      restore(client, snapshot);
      toast.error(errorText(err, 'Dismiss failed'));
    },
  });
}

interface LabelVars {
  key: string;
  isLabel: boolean;
}

export function useSetSuggestionLabel(): UseMutationResult<OkResponse, Error, LabelVars, Snapshot> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, isLabel }: LabelVars) => api.setSuggestionLabel(key, isLabel),
    onMutate: async ({ key, isLabel }) => {
      await client.cancelQueries({ queryKey: SUGGESTIONS_KEY });
      const suggestions = client.getQueryData<FollowSuggestionsResponse>(SUGGESTIONS_KEY);
      if (suggestions) client.setQueryData(SUGGESTIONS_KEY, withLabel(suggestions, key, isLabel));
      return { suggestions };
    },
    onError: (err, _vars, snapshot) => {
      restore(client, snapshot);
      toast.error(errorText(err, 'Label update failed'));
    },
  });
}

interface TierVars {
  id: number;
  tier: ArtistTier;
}

export function useTierUntiered(): UseMutationResult<UpdateArtistResult, Error, TierVars, UntieredResponse | undefined> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tier }: TierVars) => updateArtist(id, { tier }),
    onMutate: async ({ id }) => {
      await client.cancelQueries({ queryKey: UNTIERED_KEY });
      const previous = client.getQueryData<UntieredResponse>(UNTIERED_KEY);
      if (previous) client.setQueryData(UNTIERED_KEY, withoutUntiered(previous, id));
      return previous;
    },
    onError: (err, _vars, previous) => {
      if (previous) client.setQueryData(UNTIERED_KEY, previous);
      toast.error(errorText(err, 'Tier update failed'));
    },
    // Tier changes renumber every artist's ranking.
    onSuccess: () => void client.invalidateQueries({ queryKey: ['artists', 'list'] }),
  });
}
