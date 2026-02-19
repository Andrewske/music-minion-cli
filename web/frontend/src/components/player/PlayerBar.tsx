import { useEffect, useState, useRef } from 'react';
import { Play, Pause, SkipForward, SkipBack, Volume2, VolumeX, Shuffle } from 'lucide-react';
import { usePlayer } from '../../hooks/usePlayer';
import { getCurrentPosition } from '../../stores/playerStore';
import { usePlayerStore } from '../../stores/playerStore';
import { Button } from '../ui/button';
import { Slider } from '../ui/slider';
import { DeviceSelector } from './DeviceSelector';

export function PlayerBar(): JSX.Element {
  const {
    currentTrack,
    isPlaying,
    isMuted,
    isThisDeviceActive,
    shuffleEnabled,
    playbackError,
    needsUserGesture,
    volume,
    pause,
    resume,
    next,
    prev,
    seek,
    setMuted,
    setVolume,
    toggleShuffleSmooth,
    availableDevices,
    activeDeviceId,
  } = usePlayer();

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.code) {
        case 'Space':
          e.preventDefault();
          if (isPlaying) {
            pause();
          } else {
            resume();
          }
          break;
        case 'ArrowRight':
          next();
          break;
        case 'ArrowLeft':
          prev();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, pause, resume, next, prev]);

  // Progress calculation using interpolation
  const [progress, setProgress] = useState(0);
  const progressIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    // Clear existing interval
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }

    // Reset progress if no track or not playing
    if (!currentTrack?.duration || !isPlaying) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setProgress(0);
      return;
    }

    const updateProgress = (): void => {
      const pos = getCurrentPosition(usePlayerStore.getState());
      setProgress((pos / ((currentTrack.duration ?? 0) * 1000)) * 100);
    };

    updateProgress();
    progressIntervalRef.current = setInterval(updateProgress, 250); // UI update only, no state sync

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, [currentTrack?.id, currentTrack?.duration, isPlaying]);

  const activeDeviceName =
    availableDevices.find((d) => d.id === activeDeviceId)?.name ?? 'Unknown Device';

  return (
    <div className="fixed bottom-0 left-0 right-0 h-16 bg-obsidian-surface border-t border-obsidian-border flex items-center px-4 gap-4 z-50">
      {/* Track info */}
      <div className="flex items-center gap-3 w-64">
        {currentTrack && (
          <>
            <div className="truncate">
              <div className="font-medium text-white/90 truncate">
                {currentTrack.title ?? 'Not playing'}
              </div>
              <div className="text-sm text-white/60 truncate">{currentTrack.artist}</div>
            </div>
          </>
        )}
        {!currentTrack && (
          <div className="text-white/50 text-sm font-sf-mono">Not playing</div>
        )}
      </div>

      {/* Controls */}
      <div className="flex-1 flex flex-col items-center gap-1">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={prev} className="text-white/90 hover:text-white">
            <SkipBack className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={isPlaying ? pause : resume}
            className="text-white/90 hover:text-white"
          >
            {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
          </Button>
          <Button variant="ghost" size="icon" onClick={next} className="text-white/90 hover:text-white">
            <SkipForward className="h-4 w-4" />
          </Button>
        </div>
        {/* Progress bar */}
        {currentTrack && (
          <Slider
            value={[progress]}
            max={100}
            onValueChange={([v]) => {
              if (currentTrack.duration) {
                seek((v / 100) * currentTrack.duration * 1000);
              }
            }}
            className="w-96"
          />
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleShuffleSmooth}
          className={shuffleEnabled ? 'text-obsidian-accent' : 'text-white/60 hover:text-white'}
          title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
        >
          <Shuffle className="h-4 w-4" />
        </Button>
        <DeviceSelector />
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMuted(!isMuted)}
          className="text-white/90 hover:text-white"
        >
          {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
        </Button>
        <Slider
          value={[isMuted ? 0 : volume * 100]}
          max={100}
          onValueChange={([v]) => setVolume(v / 100)}
          className="w-20"
        />
      </div>

      {/* Error indicator */}
      {playbackError && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full bg-red-600 text-white text-xs px-2 py-1 rounded-t">
          {playbackError}
        </div>
      )}

      {/* iOS "tap to play" overlay */}
      {needsUserGesture && (
        <button
          onClick={resume}
          className="absolute inset-0 bg-black/50 flex items-center justify-center"
        >
          <span className="text-white">Tap to play</span>
        </button>
      )}

      {/* Playing on indicator (when not this device) */}
      {!isThisDeviceActive && currentTrack && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full bg-obsidian-accent text-white text-xs px-2 py-1 rounded-t">
          Playing on {activeDeviceName}
        </div>
      )}
    </div>
  );
}
