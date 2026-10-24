import { describe, expect, it } from 'vitest';
import {
  INITIAL_UNDO_STATE,
  dismissUndo,
  inverseMutation,
  offerUndo,
  undoMessage,
} from './undoState';
import type { UndoOffer } from './undoState';

const REMOVED: UndoOffer = { kind: 'removed', bucketId: 'b1', bucketName: 'Openers', trackId: 7 };
const ADDED: UndoOffer = { kind: 'added', bucketId: 'b2', bucketName: 'Peak', trackId: 9 };

describe('offerUndo', () => {
  it('assigns increasing ids', () => {
    const one = offerUndo(INITIAL_UNDO_STATE, REMOVED);
    const two = offerUndo(one, ADDED);
    expect(one.pending?.id).toBe(1);
    expect(two.pending).toEqual({ ...ADDED, id: 2 });
  });

  it('does not mutate the previous state', () => {
    offerUndo(INITIAL_UNDO_STATE, REMOVED);
    expect(INITIAL_UNDO_STATE.pending).toBeNull();
  });
});

describe('dismissUndo', () => {
  it('clears the matching offer', () => {
    const state = offerUndo(INITIAL_UNDO_STATE, REMOVED);
    expect(dismissUndo(state, 1).pending).toBeNull();
  });

  it('ignores a stale id so a newer offer survives', () => {
    const state = offerUndo(offerUndo(INITIAL_UNDO_STATE, REMOVED), ADDED);
    expect(dismissUndo(state, 1)).toBe(state);
  });

  it('is a no-op with nothing pending', () => {
    expect(dismissUndo(INITIAL_UNDO_STATE, 1)).toBe(INITIAL_UNDO_STATE);
  });
});

describe('undoMessage / inverseMutation', () => {
  it('describes removals and re-assigns them', () => {
    const action = { ...REMOVED, id: 1 };
    expect(undoMessage(action)).toBe('Removed from Openers');
    expect(inverseMutation(action.kind)).toBe('assign');
  });

  it('describes adds and unassigns them', () => {
    const action = { ...ADDED, id: 2 };
    expect(undoMessage(action)).toBe('Added to Peak');
    expect(inverseMutation(action.kind)).toBe('unassign');
  });
});
