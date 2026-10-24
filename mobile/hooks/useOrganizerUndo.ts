/**
 * Undo for organizer track moves. Holds one pending offer (features/organizer/
 * undoState), hides it after UNDO_VISIBLE_MS, and reverses it with the regular
 * organizer mutations: a removal is re-assigned to the same bucket, an add is
 * unassigned. No extra endpoints, so linked playlists stay in sync.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import Toast from 'react-native-toast-message';
import {
  INITIAL_UNDO_STATE,
  UNDO_VISIBLE_MS,
  dismissUndo,
  inverseMutation,
  offerUndo,
} from '../features/organizer/undoState';
import type { UndoAction, UndoOffer, UndoState } from '../features/organizer/undoState';

export interface TrackMutations {
  assignTrack: (bucketId: string, trackId: number) => Promise<unknown>;
  unassignTrack: (bucketId: string, trackId: number) => Promise<unknown>;
}

export interface OrganizerUndo {
  pending: UndoAction | null;
  offer: (offer: UndoOffer) => void;
  undo: () => Promise<void>;
}

/** Hide the current offer once its time is up (a newer offer resets the clock). */
function useAutoDismiss(state: UndoState, setState: (fn: (s: UndoState) => UndoState) => void): void {
  const id = state.pending?.id;
  useEffect(() => {
    if (id === undefined) return;
    const timer = setTimeout(() => setState((s) => dismissUndo(s, id)), UNDO_VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [id, setState]);
}

function runInverse(action: UndoAction, mutations: TrackMutations): Promise<unknown> {
  return inverseMutation(action.kind) === 'assign'
    ? mutations.assignTrack(action.bucketId, action.trackId)
    : mutations.unassignTrack(action.bucketId, action.trackId);
}

export function useOrganizerUndo(mutations: TrackMutations): OrganizerUndo {
  const [state, setState] = useState<UndoState>(INITIAL_UNDO_STATE);
  // Synchronous guard: two taps in one tick both see the same `pending`.
  const undoingRef = useRef<number | null>(null);
  useAutoDismiss(state, setState);

  const offer = useCallback((o: UndoOffer): void => setState((s) => offerUndo(s, o)), []);

  const undo = useCallback(async (): Promise<void> => {
    const action = state.pending;
    if (!action || undoingRef.current === action.id) return;
    undoingRef.current = action.id;
    setState((s) => dismissUndo(s, action.id));
    try {
      await runInverse(action, mutations);
    } catch {
      Toast.show({ type: 'error', text1: 'Undo failed', text2: 'The track was not restored' });
    }
  }, [state.pending, mutations]);

  return { pending: state.pending, offer, undo };
}
