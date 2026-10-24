/**
 * Pure state for the organizer's undo snackbar. One pending action at a time:
 * a new offer replaces the old one, and a stale timer can't clear a newer offer.
 */

/** What just happened to a track. Undo runs the opposite mutation. */
export type UndoKind = 'added' | 'removed';

export interface UndoAction {
  /** Monotonic id so timers and taps only act on the offer they belong to. */
  id: number;
  kind: UndoKind;
  bucketId: string;
  bucketName: string;
  trackId: number;
}

export interface UndoState {
  pending: UndoAction | null;
  nextId: number;
}

export type UndoOffer = Omit<UndoAction, 'id'>;

export const UNDO_VISIBLE_MS = 5000;

export const INITIAL_UNDO_STATE: UndoState = { pending: null, nextId: 1 };

/** Show a new undo offer, replacing any current one. */
export function offerUndo(state: UndoState, offer: UndoOffer): UndoState {
  return { pending: { ...offer, id: state.nextId }, nextId: state.nextId + 1 };
}

/** Drop the offer with this id; no-op if a newer offer has replaced it. */
export function dismissUndo(state: UndoState, id: number): UndoState {
  if (state.pending?.id !== id) return state;
  return { ...state, pending: null };
}

/** Snackbar text, e.g. "Removed from Openers". */
export function undoMessage(action: UndoAction): string {
  return action.kind === 'removed' ? `Removed from ${action.bucketName}` : `Added to ${action.bucketName}`;
}

/** The mutation that reverses the action: re-assign a removal, unassign an add. */
export function inverseMutation(kind: UndoKind): 'assign' | 'unassign' {
  return kind === 'removed' ? 'assign' : 'unassign';
}
