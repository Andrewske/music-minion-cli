import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Cloud, EyeOff, Heart, Music, ThumbsDown } from 'lucide-react';
import type { FeedItem, FeedRating } from '../../api/feed';
import { ArtistHoverCard } from './ArtistHoverCard';
import { FeedWaveform } from './FeedWaveform';

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '-';
  const days = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (days < 1) return '<1d';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  return `${Math.floor(days / 30)}mo`;
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${String(sec).padStart(2, '0')}`;
}

interface FeedTrackCardProps {
  item: FeedItem;
  isPlaying: boolean;
  onPlay: (item: FeedItem) => void;
  onRate: (item: FeedItem, value: FeedRating) => void;
}

export function FeedTrackCard({
  item,
  isPlaying,
  onPlay,
  onRate,
}: FeedTrackCardProps): JSX.Element {
  const [artworkFailed, setArtworkFailed] = useState(false);
  const playable = item.local_track_id !== null;
  const liked = item.status === 'liked';
  const hidden = item.status === 'hidden' || item.status === 'dismissed';
  const alreadySaved = item.in_likes || item.in_playlists;

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 rounded border transition-colors ${
        isPlaying
          ? 'bg-obsidian-accent/10 border-obsidian-accent/40'
          : 'bg-obsidian-surface border-obsidian-border hover:border-white/20'
      } ${hidden ? 'opacity-50' : ''}`}
    >
      {/* Artwork — click to play */}
      <button
        onClick={() => playable && onPlay(item)}
        disabled={!playable}
        aria-label={`Play ${item.title ?? 'track'}`}
        className="shrink-0 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {item.artwork_url && !artworkFailed ? (
          <img
            src={item.artwork_url}
            alt=""
            width={48}
            height={48}
            loading="lazy"
            onError={() => setArtworkFailed(true)}
            className="w-12 h-12 rounded object-cover"
          />
        ) : (
          <div className="w-12 h-12 rounded bg-gradient-to-br from-obsidian-accent/20 to-obsidian-surface flex items-center justify-center">
            <Music className="w-5 h-5 text-white/40" />
          </div>
        )}
      </button>

      {/* Title / artist / date */}
      <div className="min-w-0 w-56 shrink-0 text-left">
        <button
          onClick={() => playable && onPlay(item)}
          disabled={!playable}
          className="block w-full text-left disabled:cursor-not-allowed"
        >
          <div
            className={`text-sm truncate ${isPlaying ? 'text-obsidian-accent' : 'text-white'}`}
            title={item.title ?? undefined}
          >
            {item.title ?? 'Untitled'}
            {!playable && <Cloud className="inline w-3 h-3 ml-1 text-white/40" />}
          </div>
        </button>
        <div className="flex items-center gap-1.5 text-xs text-white/50">
          {item.artist.avatar_url && (
            <img
              src={item.artist.avatar_url}
              alt=""
              className="w-4 h-4 rounded-full shrink-0"
              loading="lazy"
            />
          )}
          <ArtistHoverCard artist={item.artist}>
            <Link
              to="/artists/$artistId"
              params={{ artistId: String(item.artist.id) }}
              className="truncate underline decoration-dotted decoration-white/20 underline-offset-2 hover:text-white/80 transition-colors"
            >
              {item.artist.display_name ?? item.artist.slug}
            </Link>
          </ArtistHoverCard>
          <span className="text-white/30 shrink-0">·</span>
          <span className="shrink-0" title={new Date(item.uploaded_at).toLocaleString()}>
            {formatRelativeDate(item.uploaded_at)}
          </span>
        </div>
      </div>

      {/* Waveform — click seeks when playing, plays otherwise */}
      <div className="flex-1 min-w-0 hidden md:block">
        <FeedWaveform
          localTrackId={item.local_track_id}
          durationMs={item.duration_ms}
          onActivate={() => playable && onPlay(item)}
        />
      </div>

      {hidden && (
        <span className="shrink-0 px-1.5 py-0.5 rounded font-sf-mono text-[10px] uppercase tracking-wide text-white/40 bg-white/5">
          {item.status}
        </span>
      )}

      <span className="text-xs text-white/40 font-sf-mono shrink-0 hidden sm:block">
        {formatDuration(item.duration_ms)}
      </span>

      {/* Rating buttons */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onRate(item, -1)}
          aria-label="Dismiss (counts against artist)"
          title="-1 · hide + counts against artist"
          className="p-2 rounded text-white/40 hover:text-red-400 hover:bg-red-400/10 transition-colors"
        >
          <ThumbsDown className="w-4 h-4" />
        </button>
        <button
          onClick={() => onRate(item, 0)}
          aria-label="Hide"
          title="0 · just hide"
          className="p-2 rounded text-white/40 hover:text-white hover:bg-white/10 transition-colors"
        >
          <EyeOff className="w-4 h-4" />
        </button>
        <button
          onClick={() => !liked && onRate(item, 1)}
          aria-label="Like (adds to monthly playlist)"
          title={
            alreadySaved
              ? `already in your ${item.in_likes ? 'SoundCloud likes' : 'playlists'}`
              : '+1 · like on SoundCloud + add to monthly playlist'
          }
          className={`p-2 rounded transition-colors ${
            alreadySaved
              ? 'text-red-500'
              : liked
                ? 'text-obsidian-accent'
                : 'text-white/40 hover:text-obsidian-accent hover:bg-obsidian-accent/10'
          }`}
        >
          <Heart className={`w-4 h-4 ${alreadySaved || liked ? 'fill-current' : ''}`} />
        </button>
      </div>
    </div>
  );
}
