import type { ReactElement } from 'react';
import { AlertTriangle, BarChart3 } from 'lucide-react';
import { usePareto } from '../../hooks/useArtists';

interface ParetoBannerProps {
  onReview: (threshold_ids: number[]) => void;
}

// Heuristic: if >= 10 artists are needed to reach 80%, distribution is flat enough
// that there's no actionable Pareto concentration.
const FLAT_DISTRIBUTION_THRESHOLD = 10;

export function ParetoBanner({ onReview }: ParetoBannerProps): ReactElement | null {
  const { data: pareto, isLoading, error } = usePareto();

  if (isLoading || error != null || pareto == null) return null;
  if (pareto.total_events === 0) return null;
  if (pareto.artists_producing_80pct === 0) return null;

  const isFlat = pareto.threshold_ids.length >= FLAT_DISTRIBUTION_THRESHOLD;

  if (isFlat) {
    return (
      <aside
        role="status"
        className="flex items-center gap-3 bg-white/[0.02] border border-white/10 px-4 py-3 mb-6"
      >
        <BarChart3 className="w-4 h-4 text-white/30 shrink-0" />
        <p className="font-inter text-sm text-white/40">
          Your feed is evenly distributed — no Pareto concentration.
        </p>
      </aside>
    );
  }

  return (
    <aside
      role="status"
      className="flex items-center gap-3 bg-amber-500/5 border border-amber-500/20 px-4 py-3 mb-6"
    >
      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
      <p className="flex-1 font-inter text-sm text-white/80">
        <span className="text-amber-400 font-medium tabular-nums">
          {pareto.artists_producing_80pct}
        </span>
        {' artists produce 80% of your feed volume '}
        <span className="text-white/50 font-sf-mono text-xs tabular-nums">
          · {pareto.total_events} events · last 30d
        </span>
      </p>
      <button
        type="button"
        onClick={() => onReview(pareto.threshold_ids)}
        className="font-sf-mono text-xs uppercase tracking-wider text-amber-400 hover:text-amber-300 transition-colors shrink-0"
      >
        Review them <span aria-hidden="true">→</span>
      </button>
    </aside>
  );
}
