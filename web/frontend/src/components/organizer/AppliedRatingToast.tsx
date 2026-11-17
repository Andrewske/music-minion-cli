/** Toast body after Apply rating, with an Undo action. */
export function AppliedRatingToast({ count, onUndo }: { count: number; onUndo: () => void }): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>Rated {count} tracks from bucket order</span>
      <button
        type="button"
        onClick={onUndo}
        className="px-2 py-1 text-sm font-medium rounded-sm bg-white/10 hover:bg-white/20"
      >
        Undo
      </button>
    </div>
  );
}
