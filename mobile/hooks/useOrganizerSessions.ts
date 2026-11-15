/**
 * Organizer session list + session-changing actions (new / switch / rename /
 * delete / finish). Mirrors the session half of the web usePlaylistOrganizer.
 *
 * Every action that loads a different session writes it straight into the
 * loaded-session cache (no refetch flash), so usePlaylistOrganizer and its
 * mutations follow the switch automatically.
 */
import { useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult } from '@tanstack/react-query';
import * as bucketsApi from '@music-minion/shared';
import type { BucketSession, SessionSummary } from '@music-minion/shared';
import { commitThenReplace } from '../features/organizer/sessionTransition';

/** Cache key for the session currently loaded (status 'active') for a playlist. */
export const organizerSessionKey = (playlistId: number): readonly ['organizer', 'session', number] =>
  ['organizer', 'session', playlistId] as const;

/** Cache key for the list of non-discarded sessions for a playlist. */
export const organizerSessionsKey = (playlistId: number): readonly ['organizer', 'sessions', number] =>
  ['organizer', 'sessions', playlistId] as const;

/** Session list for the switcher. Pass the sheet's visibility so it only loads when looked at. */
export function useOrganizerSessionList(
  playlistId: number,
  enabled: boolean
): { sessions: SessionSummary[]; isLoading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: organizerSessionsKey(playlistId),
    queryFn: () => bucketsApi.listSessions(playlistId),
    enabled: enabled && !!playlistId,
    staleTime: 30 * 1000,
  });
  return { sessions: data ?? [], isLoading };
}

export interface OrganizerSessionActions {
  newSession: () => Promise<BucketSession>;
  switchSession: (sessionId: string) => Promise<BucketSession>;
  renameSession: (sessionId: string, name: string | null) => Promise<void>;
  /** Deleting the loaded session resolves to its fresh replacement; any other resolves to null. */
  deleteSession: (sessionId: string) => Promise<BucketSession | null>;
  /** Finalize (discovery feedback runs server-side), then load the fresh session. */
  finishSession: () => Promise<BucketSession>;
  isChanging: boolean;
}

interface SessionCache {
  loadedId: () => string | undefined;
  /** Cancel in-flight refetches of the loaded session: they'd land with the old one. */
  cancelRefetch: () => Promise<void>;
  load: (session: BucketSession) => Promise<void>;
  /**
   * The loaded session was finished/discarded but no replacement arrived:
   * clear it (the screen shows its loader, so nothing edits a dead session)
   * and refetch get-or-create in the background.
   */
  drop: () => Promise<void>;
  refreshList: () => void;
  setName: (sessionId: string, name: string | null) => void;
}

function sessionCache(queryClient: QueryClient, playlistId: number): SessionCache {
  const key = organizerSessionKey(playlistId);
  const refreshList = (): void => {
    void queryClient.invalidateQueries({ queryKey: organizerSessionsKey(playlistId) });
  };
  const cancelRefetch = (): Promise<void> => queryClient.cancelQueries({ queryKey: key });
  return {
    loadedId: () => queryClient.getQueryData<BucketSession>(key)?.id,
    cancelRefetch,
    refreshList,
    load: async (session) => {
      await cancelRefetch();
      queryClient.setQueryData<BucketSession>(key, session);
      refreshList();
    },
    drop: async () => {
      void queryClient.resetQueries({ queryKey: key });
      refreshList();
    },
    setName: (sessionId, name) =>
      queryClient.setQueryData<BucketSession>(key, (prev) => (prev && prev.id === sessionId ? { ...prev, name } : prev)),
  };
}

export function useOrganizerSessionActions(playlistId: number): OrganizerSessionActions {
  const cache = sessionCache(useQueryClient(), playlistId);
  const loading = useLoadingMutations(playlistId, cache);

  const renameMutation = useMutation({
    mutationFn: (params: { sessionId: string; name: string | null }) =>
      bucketsApi.renameSession(params.sessionId, params.name),
    onSuccess: (_data, { sessionId, name }) => {
      cache.setName(sessionId, name);
      cache.refreshList();
    },
  });

  const { mutateAsync: rename } = renameMutation;
  return {
    ...loading,
    renameSession: useCallback(
      async (sessionId: string, name: string | null): Promise<void> => rename({ sessionId, name }),
      [rename]
    ),
  };
}

type LoadingActions = Omit<OrganizerSessionActions, 'renameSession'>;

/** Mutations that end with a different session loaded. */
function useLoadingMutations(playlistId: number, cache: SessionCache): LoadingActions {
  const loadOptions = { onMutate: cache.cancelRefetch, onSuccess: cache.load };
  const newMutation = useMutation({ mutationFn: () => bucketsApi.createNewSession(playlistId), ...loadOptions });
  const switchMutation = useMutation({ mutationFn: bucketsApi.activateSession, ...loadOptions });
  const finishMutation = useMutation({
    mutationFn: async (): Promise<BucketSession> => {
      const loadedId = cache.loadedId();
      if (!loadedId) throw new Error('No active session');
      return commitThenReplace(
        () => bucketsApi.finalizeSession(loadedId),
        () => bucketsApi.createOrResumeSession(playlistId),
        cache.drop
      );
    },
    ...loadOptions,
  });
  const deleteMutation = useDeleteMutation(playlistId, cache);
  return {
    newSession: newMutation.mutateAsync,
    switchSession: switchMutation.mutateAsync,
    finishSession: finishMutation.mutateAsync,
    deleteSession: deleteMutation.mutateAsync,
    isChanging: [newMutation, switchMutation, finishMutation, deleteMutation].some((m) => m.isPending),
  };
}

function useDeleteMutation(
  playlistId: number,
  cache: SessionCache
): UseMutationResult<BucketSession | null, Error, string> {
  return useMutation<BucketSession | null, Error, string>({
    mutationFn: async (sessionId) => {
      const wasLoaded = cache.loadedId() === sessionId;
      if (wasLoaded) await cache.cancelRefetch();
      const discard = (): Promise<void> => bucketsApi.discardSession(sessionId);
      if (!wasLoaded) return discard().then(() => null);
      // get-or-create hands back a fresh active session for the playlist.
      return commitThenReplace(discard, () => bucketsApi.createOrResumeSession(playlistId), cache.drop);
    },
    onSuccess: async (replacement) => {
      if (replacement) return cache.load(replacement);
      cache.refreshList();
    },
  });
}
