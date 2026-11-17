import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AppliedRatingToast } from './AppliedRatingToast';

function renderToast(undoResult: boolean): { onUndone: () => void; onUndoFailed: () => void } {
  const onUndone = vi.fn();
  const onUndoFailed = vi.fn();
  render(
    <AppliedRatingToast
      count={3}
      onUndo={() => Promise.resolve(undoResult)}
      onUndone={onUndone}
      onUndoFailed={onUndoFailed}
    />,
  );
  return { onUndone, onUndoFailed };
}

describe('AppliedRatingToast', () => {
  it('closes once undo succeeds', async () => {
    const { onUndone, onUndoFailed } = renderToast(true);
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    await waitFor(() => expect(onUndone).toHaveBeenCalled());
    expect(onUndoFailed).not.toHaveBeenCalled();
  });

  it('stays open with Undo re-enabled when undo fails (e.g. a newer apply exists)', async () => {
    const { onUndone, onUndoFailed } = renderToast(false);
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    await waitFor(() => expect(onUndoFailed).toHaveBeenCalled());
    expect(onUndone).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Undo' }).hasAttribute('disabled')).toBe(false);
  });
});
