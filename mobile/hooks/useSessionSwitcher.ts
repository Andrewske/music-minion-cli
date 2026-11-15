/**
 * Session switcher wiring for the organizer screen: runs a session-changing
 * action, toasts the result, and moves live organizer playback along with it.
 * Mirrors runSessionChange in web/frontend/src/pages/PlaylistOrganizer.tsx.
 *
 * Transitions are serialized: one runs at a time, including the playback
 * rebind, and `isChanging` stays true until it is fully done.
 *
 * The route param and organizer store are NOT written by the transition. They
 * follow whatever session this screen actually shows (useSyncLoadedSession),
 * through this screen's own navigation object. A late result for another
 * playlist lands in that playlist's cache and never touches this screen.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert } from 'react-native';
import { useNavigation } from 'expo-router';
import Toast from 'react-native-toast-message';
import type { NavigationProp } from '@react-navigation/native';
import type { BucketSession } from '@music-minion/shared';
import { useOrganizerSessionActions } from './useOrganizerSessions';
import { useOrganizerStore } from '../stores/organizerStore';
import { usePlayerStore } from '../stores/playerStore';
import { followSessionWithPlayback } from '../features/organizer/playbackRebind';
import { sessionLabel } from '../features/organizer/sessionSwitcher';
import { createTransitionLock, sessionToSync } from '../features/organizer/sessionTransition';
import type { TransitionLock } from '../features/organizer/sessionTransition';

/** Params of the organizer `[sessionId]` route. */
type SessionRouteParams = {
  '[sessionId]': { sessionId: string; playlistId?: string; playlistName?: string };
};

interface UseSessionSwitcherOptions {
  playlistId: number;
  playlistName: string;
  /** The session this screen shows right now. */
  loaded: BucketSession | undefined;
  /** The route's sessionId param. */
  routeSessionId: string | undefined;
  isDiscovery: boolean;
}

export interface SessionSwitcher {
  newSession: () => Promise<void>;
  switchSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, name: string | null) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  /** Asks for confirmation first (discovery playlists get a SoundCloud warning). */
  confirmFinish: () => void;
  /** True from the moment a transition starts until its playback rebind settles. */
  isChanging: boolean;
}

const errorText = (err: unknown): string => (err instanceof Error ? err.message : String(err));

const FINISH_TEXT = 'Marks this session done and starts an empty one. You can reopen it from Sessions.';
const DISCOVERY_TEXT =
  'Finishing likes tracks in linked buckets on SoundCloud and dismisses (deletes) tracks in unlinked buckets.';

async function followPlayback(leavingId: string | undefined, next: BucketSession): Promise<void> {
  try {
    const context = usePlayerStore.getState().currentContext;
    if (await followSessionWithPlayback(context, leavingId, next)) {
      Toast.show({ type: 'info', text1: `Playback now follows ${sessionLabel(next)}` });
    }
  } catch (err) {
    Toast.show({ type: 'error', text1: 'Could not move playback to the new session', text2: errorText(err) });
  }
}

/** Keep this screen's route param and the organizer store on the session it shows. */
function useSyncLoadedSession({ playlistId, playlistName, loaded, routeSessionId }: UseSessionSwitcherOptions): void {
  // This screen's own navigation object: setParams can only touch this route.
  const navigation = useNavigation<NavigationProp<SessionRouteParams>>();
  const setActiveSession = useOrganizerStore((s) => s.setActiveSession);
  const target = sessionToSync(loaded, routeSessionId, playlistId);
  useEffect(() => {
    if (!target) return;
    setActiveSession({ sessionId: target, playlistId, playlistName });
    navigation.setParams({ sessionId: target });
  }, [target, playlistId, playlistName, navigation, setActiveSession]);
}

type SessionChange = (action: () => Promise<BucketSession | null>, success: string | null, failure: string) => Promise<void>;

/** Run one transition end to end (action, toast, playback rebind) under the lock. */
async function runTransition(
  leavingId: string | undefined,
  action: () => Promise<BucketSession | null>,
  messages: { success: string | null; failure: string }
): Promise<void> {
  let next: BucketSession | null;
  try {
    next = await action();
  } catch (err) {
    Toast.show({ type: 'error', text1: messages.failure, text2: errorText(err) });
    return;
  }
  if (messages.success) Toast.show({ type: 'success', text1: messages.success });
  // Playback is server state, not screen state: rebind even if the user left the screen.
  if (next) await followPlayback(leavingId, next);
}

function useSerializedChange(loadedId: string | undefined): { run: SessionChange; busy: boolean } {
  const lockRef = useRef<TransitionLock>(createTransitionLock());
  const loadedIdRef = useRef(loadedId);
  loadedIdRef.current = loadedId;
  const [busy, setBusy] = useState(false);
  const run = useCallback<SessionChange>(async (action, success, failure) => {
    if (!lockRef.current.tryAcquire()) return;
    setBusy(true);
    try {
      await runTransition(loadedIdRef.current, action, { success, failure });
    } finally {
      lockRef.current.release();
      setBusy(false);
    }
  }, []);
  return { run, busy };
}

export function useSessionSwitcher(options: UseSessionSwitcherOptions): SessionSwitcher {
  useSyncLoadedSession(options);
  const actions = useOrganizerSessionActions(options.playlistId);
  const { run, busy } = useSerializedChange(options.loaded?.id);
  const { newSession, switchSession, deleteSession, finishSession } = actions;
  return {
    newSession: useCallback(() => run(newSession, null, 'Failed to start a new session'), [run, newSession]),
    switchSession: useCallback((id: string) => run(() => switchSession(id), null, 'Failed to load session'), [run, switchSession]),
    deleteSession: useCallback((id: string) => run(() => deleteSession(id), 'Session deleted', 'Failed to delete session'), [run, deleteSession]),
    renameSession: useRename(actions.renameSession),
    confirmFinish: useConfirmFinish(run, finishSession, options.isDiscovery),
    isChanging: busy || actions.isChanging,
  };
}

function useRename(renameSession: (id: string, name: string | null) => Promise<void>): SessionSwitcher['renameSession'] {
  return useCallback(async (id: string, name: string | null): Promise<void> => {
    await renameSession(id, name).catch((err: unknown) => {
      Toast.show({ type: 'error', text1: 'Failed to rename session', text2: errorText(err) });
    });
  }, [renameSession]);
}

function useConfirmFinish(run: SessionChange, finishSession: () => Promise<BucketSession>, isDiscovery: boolean): () => void {
  return useCallback((): void => {
    Alert.alert('Finish session?', isDiscovery ? `${FINISH_TEXT}\n\n${DISCOVERY_TEXT}` : FINISH_TEXT, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Finish', onPress: () => void run(finishSession, 'Session finished', 'Failed to finish session') },
    ]);
  }, [run, finishSession, isDiscovery]);
}
