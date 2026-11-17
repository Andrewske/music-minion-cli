import { useState } from 'react';

interface AppliedRatingToastProps {
  count: number;
  /** Resolves true when the undo went through. */
  onUndo: () => Promise<boolean>;
  onUndone: () => void;
  /** Undo failed (e.g. a newer apply must be undone first): keep the toast for a retry. */
  onUndoFailed: () => void;
}

/** Toast body after Apply rating. Closes only once Undo succeeds. */
export function AppliedRatingToast({ count, onUndo, onUndone, onUndoFailed }: AppliedRatingToastProps): JSX.Element {
  const [isUndoing, setIsUndoing] = useState(false);

  const handleUndo = async (): Promise<void> => {
    setIsUndoing(true);
    if (await onUndo()) {
      onUndone();
      return;
    }
    setIsUndoing(false);
    onUndoFailed();
  };

  return (
    <div className="flex items-center justify-between gap-3">
      <span>Rated {count} tracks from bucket order</span>
      <button
        type="button"
        onClick={handleUndo}
        disabled={isUndoing}
        className="px-2 py-1 text-sm font-medium rounded-sm bg-white/10 hover:bg-white/20 disabled:opacity-50"
      >
        {isUndoing ? 'Undoing…' : 'Undo'}
      </button>
    </div>
  );
}
