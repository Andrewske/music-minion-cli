import type { ReactNode } from 'react';
import { Heart, Meh, ThumbsDown } from 'lucide-react';
import type { FeedDecision, FeedVerdict } from '../../api/feed';

interface VerdictSpec {
  verdict: FeedVerdict;
  title: string;
  label: string;
  icon: (filled: boolean) => ReactNode;
}

const VERDICT_SPECS: readonly VerdictSpec[] = [
  {
    verdict: 'nope',
    title: 'Nope',
    label: 'Nope; clear pass, counts against this recommendation',
    icon: () => <ThumbsDown className="h-4 w-4" />,
  },
  {
    verdict: 'not_quite',
    title: 'Not quite',
    label: 'Not quite; close but not a keep',
    icon: () => <Meh className="h-4 w-4" />,
  },
  {
    verdict: 'keep',
    title: 'Keep',
    label: 'Keep; like on SoundCloud and add to monthly playlist',
    icon: (filled) => <Heart className={`h-4 w-4 ${filled ? 'fill-current' : ''}`} />,
  },
];

interface VerdictButtonsProps {
  current: FeedDecision | null;
  /** Keep renders as active when the track is already liked elsewhere. */
  hearted?: boolean;
  disabled?: boolean;
  showLabels?: boolean;
  onDecide: (verdict: FeedVerdict) => void;
}

/** Nope / Not quite / Keep; the current verdict is pressed and not re-sendable. */
export function VerdictButtons({
  current,
  hearted = false,
  disabled = false,
  showLabels = false,
  onDecide,
}: VerdictButtonsProps): JSX.Element {
  return (
    <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="Feed decisions">
      {VERDICT_SPECS.map((spec) => {
        const active = current === spec.verdict || (spec.verdict === 'keep' && hearted);
        return (
          <button
            key={spec.verdict}
            type="button"
            onClick={() => onDecide(spec.verdict)}
            disabled={disabled || current === spec.verdict}
            aria-label={spec.label}
            aria-pressed={active}
            title={spec.title}
            className={`flex min-h-10 min-w-10 items-center justify-center gap-1.5 rounded p-2 text-xs transition-colors focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent disabled:cursor-default ${
              active ? 'bg-obsidian-accent/15 text-obsidian-accent' : 'text-white/45 hover:bg-white/10 hover:text-white disabled:opacity-50'
            }`}
          >
            {spec.icon(active)}
            {showLabels && <span>{spec.title}</span>}
          </button>
        );
      })}
    </div>
  );
}
