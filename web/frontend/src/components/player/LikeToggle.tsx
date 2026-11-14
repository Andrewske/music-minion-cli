import { Heart } from 'lucide-react';
import { toast } from 'sonner';
import { usePlayerStore } from '../../stores/playerStore';

/**
 * Player-bar heart that likes / unlikes the current track on SoundCloud (the
 * Keep's durable like job, no Keep verdict). Hidden for local-only tracks.
 */
export function LikeToggle({ className = 'h-4 w-4' }: { className?: string }): JSX.Element | null {
  const canLike = usePlayerStore((s) => Boolean(s.currentTrack?.soundcloud_id));
  const liked = usePlayerStore((s) => Boolean(s.currentTrack?.sc_liked));
  const setLiked = usePlayerStore((s) => s.setLiked);
  if (!canLike) return null;
  const toggle = (): void => {
    setLiked(!liked).catch((err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'SoundCloud like failed');
    });
  };
  const label = liked ? 'Unlike on SoundCloud' : 'Like on SoundCloud';
  return (
    <button type="button" onClick={toggle} aria-label={label} aria-pressed={liked} title={label} className="inline-flex shrink-0">
      <Heart className={`${className} ${liked ? 'text-red-500 fill-current' : 'text-white/40 hover:text-white/80'}`} />
    </button>
  );
}
