import type { ReactElement } from 'react';
import { HardDrive, Heart, ListMusic, Play } from 'lucide-react';
import type { Track } from '@music-minion/shared';
import type { ArtistLibraryTrack } from '../../api/artists';
import { usePlayerStore } from '../../stores/playerStore';

/** Playlist name colors keyed by playlists.library. */
const LIBRARY_COLORS: Record<string, string> = {
  local: 'text-emerald-400',
  soundcloud: 'text-orange-400',
  spotify: 'text-green-500',
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '–:––';
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function toTrack(t: ArtistLibraryTrack): Track {
  return {
    id: t.id,
    title: t.title,
    artist: t.artist,
    album: t.album ?? undefined,
    duration: t.duration ?? undefined,
  };
}

export const isSaved = (t: ArtistLibraryTrack): boolean =>
  t.is_liked || t.playlists.length > 0;

interface TrackRowProps {
  track: ArtistLibraryTrack;
  isPlaying: boolean;
  onPlay: (track: ArtistLibraryTrack) => void;
}

function TrackRow({ track, isPlaying, onPlay }: TrackRowProps): ReactElement {
  return (
    <button
      onClick={() => onPlay(track)}
      className={`group w-full flex items-center gap-3 px-3 py-2 rounded border text-left transition-colors ${
        isPlaying
          ? 'bg-obsidian-accent/10 border-obsidian-accent/40'
          : 'bg-obsidian-surface border-obsidian-border hover:border-white/20'
      }`}
    >
      <span className="shrink-0 w-8 h-8 rounded bg-white/5 flex items-center justify-center">
        <Play
          className={`w-3.5 h-3.5 ${
            isPlaying ? 'text-obsidian-accent' : 'text-white/30 group-hover:text-white'
          }`}
        />
      </span>
      <span className="min-w-0 flex-1">
        <span
          className={`block text-sm truncate ${isPlaying ? 'text-obsidian-accent' : 'text-white'}`}
        >
          {track.title}
        </span>
        {track.playlists.length > 0 && (
          <span className="flex items-center gap-1 mt-0.5 text-xs text-white/40 truncate">
            <ListMusic className="w-3 h-3 shrink-0" />
            <span className="truncate">
              {track.playlists.map((p, i) => (
                <span key={`${p.library}:${p.name}`}>
                  {i > 0 && <span className="text-white/25"> · </span>}
                  <span
                    className={LIBRARY_COLORS[p.library] ?? 'text-white/40'}
                    title={`${p.library} playlist`}
                  >
                    {p.name}
                  </span>
                </span>
              ))}
            </span>
          </span>
        )}
      </span>
      {track.local_path != null && (
        <span title="Local file on disk" className="shrink-0 flex">
          <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
        </span>
      )}
      {track.is_liked && <Heart className="w-3.5 h-3.5 shrink-0 text-red-500 fill-current" />}
      {track.play_count > 0 && (
        <span className="text-xs text-white/30 font-sf-mono shrink-0">{track.play_count}×</span>
      )}
      <span className="text-xs text-white/40 font-sf-mono shrink-0">
        {formatDuration(track.duration)}
      </span>
    </button>
  );
}

interface ArtistTrackSectionsProps {
  tracks: ArtistLibraryTrack[];
}

/** Saved-first track sections with sequential play-from-row queueing. */
export function ArtistTrackSections({ tracks }: ArtistTrackSectionsProps): ReactElement {
  const play = usePlayerStore((s) => s.play);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);

  const handlePlay = (track: ArtistLibraryTrack): void => {
    // Sequential from the clicked row through the rest of the sorted list.
    const index = tracks.findIndex((t) => t.id === track.id);
    const trackIds = tracks.slice(index).map((t) => t.id);
    void play(toTrack(track), { type: 'feed', track_ids: trackIds, shuffle: false });
  };

  const saved = tracks.filter(isSaved);
  const rest = tracks.filter((t) => !isSaved(t));

  if (tracks.length === 0) {
    return (
      <p className="font-sf-mono text-sm text-white/40 py-8 text-center">
        No tracks from this artist in your library yet.
      </p>
    );
  }

  return (
    <>
      {saved.length > 0 && (
        <section className="space-y-1.5">
          <h2 className="font-sf-mono text-xs uppercase tracking-widest text-obsidian-accent">
            Liked & in playlists · {saved.length}
          </h2>
          {saved.map((t) => (
            <TrackRow
              key={t.id}
              track={t}
              isPlaying={t.id === currentTrackId}
              onPlay={handlePlay}
            />
          ))}
        </section>
      )}

      {rest.length > 0 && (
        <section className="space-y-1.5">
          <h2 className="font-sf-mono text-xs uppercase tracking-widest text-white/40">
            Library · {rest.length}
          </h2>
          {rest.map((t) => (
            <TrackRow
              key={t.id}
              track={t}
              isPlaying={t.id === currentTrackId}
              onPlay={handlePlay}
            />
          ))}
        </section>
      )}
    </>
  );
}
