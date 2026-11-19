import { useCallback, useState } from 'react';
import { usePlayerStore } from '../../stores/playerStore';
import { WaveformPlayer } from '../WaveformPlayer';
import type { Bucket } from '../../api/buckets';
import type { TrackReposter } from '../../types';
import { NotesToggle, TrackNotesPanel } from './TrackNotes';
import { PlaylistPicker } from './PlaylistPicker';
import { Backdrop, TrackBannerInfo } from './TrackBannerParts';

interface CurrentTrackBannerProps {
  buckets: Bucket[];
  trackDate?: string;
  reposters?: TrackReposter[];
  artworkUrl?: string;
  scLiked?: boolean;
  soundcloudUrl?: string;
  bpm?: number;
  keySignature?: string;
  genre?: string | null;
  onGenreChange: (trackId: number, genre: string | null) => void;
  emojis?: string[];
  onEmojisChange: (trackId: number, emojis: string[]) => void;
  /** The playlist being organized; hidden from the add-to-playlist picker. */
  playlistId: number;
}

export function CurrentTrackBanner({
  buckets,
  trackDate,
  reposters,
  artworkUrl,
  scLiked,
  soundcloudUrl,
  bpm,
  keySignature,
  genre,
  onGenreChange,
  emojis,
  onEmojisChange,
  playlistId,
}: CurrentTrackBannerProps): JSX.Element {
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const pause = usePlayerStore((s) => s.pause);
  const resume = usePlayerStore((s) => s.resume);
  const [notesOpen, setNotesOpen] = useState(false);

  const handleTogglePlayPause = useCallback((): void => {
    if (isPlaying) {
      pause();
    } else {
      resume();
    }
  }, [isPlaying, pause, resume]);

  if (!currentTrack) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border rounded-lg p-4 mb-4">
        <div className="text-white/50 text-sm text-center">
          No track playing. Click a track below to start.
        </div>
      </div>
    );
  }

  return (
    <div className="relative bg-obsidian-surface border border-obsidian-border rounded-lg mb-4">
      <Backdrop trackId={currentTrack.id} artworkUrl={artworkUrl} title={currentTrack.title} />

      <div className="relative p-4">
        <div className="mb-3">
          <TrackBannerInfo
            trackId={currentTrack.id}
            title={currentTrack.title}
            artist={currentTrack.artist}
            artworkUrl={artworkUrl}
            trackDate={trackDate}
            reposters={reposters}
            scLiked={scLiked}
            soundcloudUrl={soundcloudUrl}
            bpm={bpm}
            keySignature={keySignature}
            genre={genre}
            onGenreChange={(next) => onGenreChange(currentTrack.id, next)}
            emojis={emojis}
            onEmojisChange={(next) => onEmojisChange(currentTrack.id, next)}
          />
        </div>

        {/* Waveform player */}
        <div className="h-16 mb-3">
          <WaveformPlayer
            track={currentTrack}
            isPlaying={isPlaying}
            onTogglePlayPause={handleTogglePlayPause}
          />
        </div>

        {/* Keyboard/tap hints */}
        <div className="flex items-center justify-between text-xs">
          {/* Desktop hint */}
          <div className="hidden md:block text-white/40">
            Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded-sm text-white/60">Shift</kbd> +{' '}
            <kbd className="px-1.5 py-0.5 bg-white/10 rounded-sm text-white/60">1</kbd>-<kbd className="px-1.5 py-0.5 bg-white/10 rounded-sm text-white/60">{Math.min(buckets.length, 9)}</kbd> to assign to bucket
          </div>

          {/* Mobile hint */}
          <div className="md:hidden text-white/40">
            Tap bucket below to assign
          </div>

          {buckets.length === 0 && (
            <div className="text-amber-400/80">
              Create buckets first to assign tracks
            </div>
          )}

          <div className="ml-auto flex items-center gap-1">
            <PlaylistPicker
              key={currentTrack.id}
              trackId={currentTrack.id}
              excludePlaylistId={playlistId}
            />
            <NotesToggle open={notesOpen} onToggle={() => setNotesOpen((prev) => !prev)} />
          </div>
        </div>

        {notesOpen && <TrackNotesPanel trackId={currentTrack.id} />}
      </div>
    </div>
  );
}
