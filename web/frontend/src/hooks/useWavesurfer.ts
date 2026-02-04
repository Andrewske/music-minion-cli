import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';
import { formatError } from '../utils/formatError';

interface UseWavesurferOptions {
  trackId: number;
  isPlaying: boolean;  // Explicit control instead of isActive
  onFinish?: () => void;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
  onTimeUpdate?: (currentTime: number) => void;
}

function createWavesurferConfig(container: HTMLDivElement) {
  return {
    container,
    waveColor: '#475569', // slate-600
    progressColor: '#10b981', // emerald-500
    cursorColor: '#10b981', // emerald-500
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    height: 64,
    normalize: true,
    backend: 'MediaElement' as const,
  };
}

export function useWavesurfer({ trackId, isPlaying, onFinish, onReady, onSeek, onTimeUpdate }: UseWavesurferOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const lastPositionRef = useRef<number>(0); // Store last playback position
  const lastFinishTimeRef = useRef<number>(0); // Debounce rapid finish triggers
  const prevTrackIdRef = useRef<number>(trackId);

  // Use refs for callbacks and state to prevent re-initialization
  const onFinishRef = useRef(onFinish);
  const onReadyRef = useRef(onReady);
  const onSeekRef = useRef(onSeek);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const isPlayingRef = useRef(isPlaying);

  // Update refs when values change
  useEffect(() => {
    onFinishRef.current = onFinish;
  }, [onFinish]);
  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);
  useEffect(() => {
    onSeekRef.current = onSeek;
  }, [onSeek]);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  }, [onTimeUpdate]);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  const handleReady = useCallback((duration: number): void => {
    setDuration(duration);
    onReadyRef.current?.(duration);
  }, []);

  const handleSeek = useCallback((progress: number): void => {
    onSeekRef.current?.(progress);
  }, []);

  const handleFinish = useCallback((): void => {
    // Debounce rapid finish triggers with 2 second cooldown to prevent
    // multiple finish events from firing in quick succession, which can
    // cause erratic behavior in comparison mode track switching
    const now = Date.now();
    if (now - lastFinishTimeRef.current < 2000) {
      return;
    }
    lastFinishTimeRef.current = now;
    onFinishRef.current?.();
  }, []);

  const initWavesurfer = useCallback(async (abortSignal: AbortSignal) => {
    if (!containerRef.current) return;

    try {
      setError(null);

      // Defensive cleanup: destroy existing instance before creating new one
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }

      // Check if aborted before async operations
      if (abortSignal.aborted) return;

      // Try to load waveform first
      let waveformData = null;
      try {
        waveformData = await getWaveformData(trackId);
      } catch {
        // Graceful degradation to basic playback without visualization
      }

      // Check if aborted after waveform fetch
      if (abortSignal.aborted) return;

      // Create WaveSurfer instance
      const wavesurfer = WaveSurfer.create(createWavesurferConfig(containerRef.current));

      // Load audio with or without waveform
      const streamUrl = getStreamUrl(trackId);
      if (waveformData?.peaks) {
        wavesurfer.load(streamUrl, [waveformData.peaks]);
      } else {
        wavesurfer.load(streamUrl); // Basic playback without visualization
      }

      // Set up event listeners
      wavesurfer.on('ready', () => {
        handleReady(wavesurfer.getDuration());
        // Play if currently playing
        if (isPlayingRef.current) {
          wavesurfer.play().catch(() => {});
        }
      });

      wavesurfer.on('error', (error) => {
        setError(formatError(error));
      });

        wavesurfer.on('pause', () => {
          lastPositionRef.current = wavesurfer.getCurrentTime(); // Store position on pause
        });
        wavesurfer.on('finish', handleFinish);

        wavesurfer.on('timeupdate', () => {
          const time = wavesurfer.getCurrentTime();
          setCurrentTime(time);
          lastPositionRef.current = time; // Update resume position during playback
        });

        wavesurfer.on('interaction', () => {
          const time = wavesurfer.getCurrentTime();
          setCurrentTime(time);
          lastPositionRef.current = time; // Update resume position on user interaction
          const progress = time / wavesurfer.getDuration();
          handleSeek(progress);
        });

      // Final abort check before committing the instance
      if (abortSignal.aborted) {
        wavesurfer.destroy();
        return;
      }

      wavesurferRef.current = wavesurfer;
    } catch (error) {
      // Don't set error if operation was aborted
      if (abortSignal.aborted) return;

      // Audio loading failed - show error to user
      setError(formatError(error));
    }
  }, [trackId, handleReady, handleSeek, handleFinish]);

  useEffect(() => {
    if (!containerRef.current || !trackId) return;

    // Only reset position when track ACTUALLY changes, not on callback updates
    const trackChanged = prevTrackIdRef.current !== trackId;
    if (trackChanged) {
      lastPositionRef.current = 0;
      prevTrackIdRef.current = trackId;
    }

    // AbortController to cancel async operations on cleanup
    const abortController = new AbortController();

    // ESLint warning is a false positive: initWavesurfer performs async initialization
    // that sets state (error, isPlaying, currentTime) as side effects. This is safe
    // because it only runs when trackId changes, not in response to state changes.
    // isPlaying changes are handled separately by the effect below
    initWavesurfer(abortController.signal);

    return () => {
      // Abort any in-flight async operations
      abortController.abort();

      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackId, initWavesurfer]); // isPlaying handled by separate effect below

  // Effect responds to isPlaying changes
  useEffect(() => {
    if (!wavesurferRef.current) return;

    if (isPlaying && !wavesurferRef.current.isPlaying()) {
      wavesurferRef.current.play().catch((err) => {
        console.warn('Play failed:', err);
      });
    } else if (!isPlaying && wavesurferRef.current.isPlaying()) {
      wavesurferRef.current.pause();
    }
  }, [isPlaying]);

  const togglePlayPause = (): void => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const seekToPercent = useCallback((percent: number): void => {
    if (wavesurferRef.current) {
      wavesurferRef.current.seekTo(percent / 100);
    }
  }, []);

  const seekRelative = useCallback((seconds: number): void => {
    if (wavesurferRef.current) {
      const currentTime = wavesurferRef.current.getCurrentTime();
      const duration = wavesurferRef.current.getDuration();
      const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
      wavesurferRef.current.seekTo(newTime / duration);
    }
  }, []);

  const retryLoad = useCallback((): void => {
    // FIX: Destroy old instance BEFORE creating new one
    if (wavesurferRef.current) {
      wavesurferRef.current.destroy();
      wavesurferRef.current = null;
    }
    setError(null);
    // Re-trigger initialization with new AbortController
    const abortController = new AbortController();
    initWavesurfer(abortController.signal);
  }, [initWavesurfer]);

  // Listen for seek commands from IPC
  useEffect(() => {
    const handleSeekPos = () => {
      if (wavesurferRef.current && isPlaying) {
        seekRelative(10);
      }
    };

    const handleSeekNeg = () => {
      if (wavesurferRef.current && isPlaying) {
        seekRelative(-10);
      }
    };

    window.addEventListener('music-minion-seek-pos', handleSeekPos);
    window.addEventListener('music-minion-seek-neg', handleSeekNeg);

    return () => {
      window.removeEventListener('music-minion-seek-pos', handleSeekPos);
      window.removeEventListener('music-minion-seek-neg', handleSeekNeg);
    };
  }, [isPlaying, seekRelative]);

  // Listen for seek percent commands
  useEffect(() => {
    const handleSeekPercent = (e: CustomEvent<number>) => {
      seekToPercent(e.detail);
    };
    window.addEventListener('music-minion-seek-percent', handleSeekPercent as EventListener);
    return () => window.removeEventListener('music-minion-seek-percent', handleSeekPercent as EventListener);
  }, [seekToPercent]);

  return {
    containerRef,
    currentTime,
    duration,
    error,
    retryLoad,
    seekToPercent,
    seekRelative,
    togglePlayPause,
  };
}