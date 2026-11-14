/**
 * Session switcher wiring for the organizer screen: runs a session-changing
 * action, toasts the result, keeps the route param + organizer store on the
 * newly loaded session, and moves live organizer playback along with it.
 * Mirrors runSessionChange in web/frontend/src/pages/PlaylistOrganizer.tsx.
 */
import { useCallback } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import Toast from 'react-native-toast-message';
import type { BucketSession } from '@music-minion/shared';
import { useOrganizerSessionActions } from './useOrganizerSessions';
import { useOrganizerStore } from '../stores/organizerStore';
import { usePlayerStore } from '../stores/playerStore';
import { followSessionWithPlayback } from '../features/organizer/playbackRebind';
import { sessionLabel } from '../features/organizer/sessionSwitcher';

interface UseSessionSwitcherOptions {
  playlistId: number;
  playlistName: string;
  /** The session loaded right now (the one being left by a change). */
  loadedId: string | undefined;
  isDiscovery: boolean;
}

export interface SessionSwitcher {
  newSession: () => Promise<void>;
  switchSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, name: string | null) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  /** Asks for confirmation first (discovery playlists get a SoundCloud warning). */
  confirmFinish: () => void;
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

type SessionChange = (action: () => Promise<BucketSession | null>, success: string | null, failure: string) => Promise<void>;

function useRunSessionChange({ playlistId, playlistName, loadedId }: UseSessionSwitcherOptions): SessionChange {
  const setActiveSession = useOrganizerStore((s) => s.setActiveSession);
  return useCallback(
    async (action, success, failure) => {
      let next: BucketSession | null;
      try {
        next = await action();
      } catch (err) {
        Toast.show({ type: 'error', text1: failure, text2: errorText(err) });
        return;
      }
      if (success) Toast.show({ type: 'success', text1: success });
      if (!next) return;
      setActiveSession({ sessionId: next.id, playlistId, playlistName });
      router.setParams({ sessionId: next.id });
      await followPlayback(loadedId, next);
    },
    [playlistId, playlistName, loadedId, setActiveSession]
  );
}

export function useSessionSwitcher(options: UseSessionSwitcherOptions): SessionSwitcher {
  const actions = useOrganizerSessionActions(options.playlistId);
  const run = useRunSessionChange(options);
  const { newSession, switchSession, deleteSession, finishSession, renameSession } = actions;
  return {
    newSession: useCallback(() => run(newSession, null, 'Failed to start a new session'), [run, newSession]),
    switchSession: useCallback((id: string) => run(() => switchSession(id), null, 'Failed to load session'), [run, switchSession]),
    deleteSession: useCallback((id: string) => run(() => deleteSession(id), 'Session deleted', 'Failed to delete session'), [run, deleteSession]),
    renameSession: useCallback(async (id: string, name: string | null): Promise<void> => {
      await renameSession(id, name).catch((err: unknown) => {
        Toast.show({ type: 'error', text1: 'Failed to rename session', text2: errorText(err) });
      });
    }, [renameSession]),
    confirmFinish: useConfirmFinish(run, finishSession, options.isDiscovery),
    isChanging: actions.isChanging,
  };
}

function useConfirmFinish(run: SessionChange, finishSession: () => Promise<BucketSession>, isDiscovery: boolean): () => void {
  return useCallback((): void => {
    Alert.alert('Finish session?', isDiscovery ? `${FINISH_TEXT}\n\n${DISCOVERY_TEXT}` : FINISH_TEXT, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Finish', onPress: () => void run(finishSession, 'Session finished', 'Failed to finish session') },
    ]);
  }, [run, finishSession, isDiscovery]);
}
