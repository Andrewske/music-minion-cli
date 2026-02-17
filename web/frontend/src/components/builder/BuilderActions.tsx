interface BuilderActionsProps {
  playlistType: 'manual' | 'smart';
  onAdd?: () => void;
  onSkip: () => void;
  isAddingTrack?: boolean;
  isSkippingTrack: boolean;
}

/**
 * Type-aware action buttons for playlist builders.
 * - Manual: "Add" (primary, obsidian-accent border) + "Skip" (secondary)
 * - Smart: "Skip" only (no Add since tracks are auto-included by filters)
 */
export function BuilderActions({
  playlistType,
  onAdd,
  onSkip,
  isAddingTrack = false,
  isSkippingTrack,
}: BuilderActionsProps): JSX.Element {
  const isDisabled = isAddingTrack || isSkippingTrack;

  return (
    <div className="flex gap-4 justify-center">
      {playlistType === 'manual' && onAdd && (
        <button
          onClick={onAdd}
          disabled={isDisabled}
          className="px-8 md:px-12 py-3 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black disabled:opacity-30
            transition-all text-sm tracking-wider"
        >
          {isAddingTrack ? '...' : 'Add'}
        </button>
      )}
      <button
        onClick={onSkip}
        disabled={isDisabled}
        className="px-8 md:px-12 py-3 border border-white/20 text-white/60
          hover:border-white/40 hover:text-white disabled:opacity-30
          transition-all text-sm tracking-wider"
      >
        {isSkippingTrack ? '...' : 'Skip'}
      </button>
    </div>
  );
}
