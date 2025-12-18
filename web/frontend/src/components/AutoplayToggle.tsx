import { useComparisonStore } from '../stores/comparisonStore';

export function AutoplayToggle() {
  const { autoplay, setAutoplay } = useComparisonStore();

  return (
    <div className="flex items-center gap-2">
      <label className="flex items-center gap-2 text-xs font-medium text-slate-300 hover:text-slate-100 transition-colors cursor-pointer">
        <input
          type="checkbox"
          checked={autoplay}
          onChange={(e) => setAutoplay(e.target.checked)}
          className="w-4 h-4 text-indigo-500 bg-slate-800 border-slate-600 rounded focus:ring-indigo-500 focus:ring-2 focus:outline-none"
        />
        Autoplay
      </label>
    </div>
  );
}