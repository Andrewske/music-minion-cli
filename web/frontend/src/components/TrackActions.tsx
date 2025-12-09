interface TrackActionsProps {
  trackId: number;
  onArchive: (trackId: number) => void;
  onWinner: (trackId: number) => void;
  isLoading: boolean;
}

export function TrackActions({ trackId, onArchive, onWinner, isLoading }: TrackActionsProps) {
  return (
    <div className="hidden lg:flex justify-between mt-4 gap-4 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        onClick={() => onArchive(trackId)}
        disabled={isLoading}
        className="flex-1 bg-slate-800 text-rose-400 py-3 rounded-xl font-semibold hover:bg-slate-700 hover:text-rose-300 transition-colors border border-slate-700"
      >
        Archive
      </button>
      <button
        onClick={() => onWinner(trackId)}
        disabled={isLoading}
        className="flex-1 bg-emerald-600 text-white py-3 rounded-xl font-bold hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-900/50"
      >
        Winner
      </button>
    </div>
  );
}
