import { useState } from 'react';

interface TrackArtworkProps {
  trackId: number;
  size?: number;
  className?: string;
}

export function TrackArtwork({ trackId, size = 48, className = '' }: TrackArtworkProps): JSX.Element {
  const [failed, setFailed] = useState(false);

  const src = `/api/tracks/${trackId}/artwork`;

  if (failed) {
    return (
      <div
        className={`shrink-0 rounded bg-gradient-to-br from-obsidian-accent/20 to-obsidian-surface flex items-center justify-center ${className}`}
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        <span className="text-white/30" style={{ fontSize: size * 0.4 }}>♪</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      width={size}
      height={size}
      className={`shrink-0 rounded object-cover ${className}`}
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}
