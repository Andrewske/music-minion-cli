import { Heart } from 'lucide-react';
import type { ScLikeState } from '../api/feed';

const LABELS: Record<Exclude<ScLikeState, 'none'>, string> = {
  liked: 'Liked on SoundCloud',
  pending: 'SoundCloud like pending',
  failed: 'SoundCloud like failed',
};

const TONES: Record<Exclude<ScLikeState, 'none'>, string> = {
  liked: 'text-red-500 fill-current',
  pending: 'text-amber-300 animate-pulse',
  failed: 'text-red-400/70',
};

interface ScLikeHeartProps {
  state: ScLikeState;
  className?: string;
}

/** The one red heart: filled when the track is in SoundCloud likes; pending/failed while a keep's like is in flight. */
export function ScLikeHeart({ state, className = 'h-4 w-4' }: ScLikeHeartProps): JSX.Element | null {
  if (state === 'none') return null;
  return (
    <span role="img" aria-label={LABELS[state]} title={LABELS[state]} data-sc-like={state} className="inline-flex shrink-0">
      <Heart className={`${className} ${TONES[state]}`} />
    </span>
  );
}
