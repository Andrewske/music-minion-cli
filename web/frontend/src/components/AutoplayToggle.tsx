import { useComparisonStore } from '../stores/comparisonStore';
import { Switch } from './ui/switch';

export function AutoplayToggle() {
  const { autoplay, setAutoplay } = useComparisonStore();

  return (
    <div className="flex items-center gap-2">
      <Switch
        id="autoplay"
        checked={autoplay}
        onCheckedChange={setAutoplay}
      />
      <label
        htmlFor="autoplay"
        className="text-xs font-medium text-slate-300 hover:text-slate-100 transition-colors cursor-pointer"
      >
        Autoplay
      </label>
    </div>
  );
}