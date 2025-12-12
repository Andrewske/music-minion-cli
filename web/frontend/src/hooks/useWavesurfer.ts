import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';
import { formatError } from '../utils/formatError';

interface UseWavesurferOptions {
  trackId: number;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
  /**
   * Callback fired when audio playback reaches the end.
   * Used for comparison mode to automatically switch between tracks,
   * creating a seamless looping experience for track comparison.
   */
  onFinish?: () => void;
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

export function useWavesurfer({ trackId, onReady, onSeek, isActive = false, onFinish }: UseWavesurferOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const lastPositionRef = useRef<number>(0); // Store last playback position
  const lastFinishTimeRef = useRef<number>(0); // Debounce rapid finish triggers

  const handleReady = useCallback((duration: number) => {
    setDuration(duration);
    onReady?.(duration);
  }, [onReady]);

  const handleSeek = useCallback((progress: number) => {
    onSeek?.(progress);
  }, [onSeek]);

  const handleFinish = useCallback(() => {
    // Debounce rapid finish triggers with 2 second cooldown to prevent
    // multiple finish events from firing in quick succession, which can
    // cause erratic behavior in comparison mode track switching
    const now = Date.now();
    if (now - lastFinishTimeRef.current < 2000) {
      return;
    }
    lastFinishTimeRef.current = now;
    setIsPlaying(false);
    onFinish?.();
  }, [onFinish]);

  const initWavesurfer = useCallback(async (abortSignal: AbortSignal, shouldAutoplay: boolean) => {
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

        // Autoplay if requested
        if (shouldAutoplay) {
          wavesurfer.play().catch(() => {
            // Autoplay blocked by browser - user must interact first
          });
        }
      });

      wavesurfer.on('error', (error) => {
        setError(formatError(error));
      });

       wavesurfer.on('play', () => setIsPlaying(true));
       wavesurfer.on('pause', () => setIsPlaying(false));
        wavesurfer.on('finish', handleFinish);

       wavesurfer.on('audioprocess', () => {
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

    // Reset resume position when track changes
    lastPositionRef.current = 0;

    // AbortController to cancel async operations on cleanup
    const abortController = new AbortController();

    // ESLint warning is a false positive: initWavesurfer performs async initialization
    // that sets state (error, isPlaying, currentTime) as side effects. This is safe
    // because it only runs when trackId changes, not in response to state changes.
    // isActive changes are handled separately by the effect below (lines 179-199).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    initWavesurfer(abortController.signal, isActive);

    return () => {
      // Abort any in-flight async operations
      abortController.abort();

      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [trackId, initWavesurfer]); // isActive handled by separate effect (lines 179-199)

  // Watch for isActive changes to pause/play accordingly
  const prevIsActive = useRef(isActive);

  useEffect(() => {
    if (!wavesurferRef.current) return;

    if (isActive && !prevIsActive.current) {
      // Became active - resume from last position and play
      if (duration > 0 && lastPositionRef.current > 0) {
        wavesurferRef.current.seekTo(lastPositionRef.current / duration);
      }
      wavesurferRef.current.play().catch(() => {
        // Play failed - likely browser autoplay policy
      });
    } else if (!isActive && prevIsActive.current) {
      // Became inactive - pause and store current position
      if (wavesurferRef.current.isPlaying()) {
        wavesurferRef.current.pause();
      }
      lastPositionRef.current = wavesurferRef.current.getCurrentTime();
    }

    prevIsActive.current = isActive;
  }, [isActive, duration]);

  const togglePlayPause = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const seekToPercent = (percent: number) => {
    if (wavesurferRef.current) {
      wavesurferRef.current.seekTo(percent / 100);
    }
  };

  const retryLoad = useCallback(() => {
    // FIX: Destroy old instance BEFORE creating new one
    if (wavesurferRef.current) {
      wavesurferRef.current.destroy();
      wavesurferRef.current = null;
    }
    setError(null);
    // Re-trigger initialization with new AbortController
    const abortController = new AbortController();
    initWavesurfer(abortController.signal, isActive);
  }, [initWavesurfer, isActive]);

  return {
    containerRef,
    isPlaying,
    currentTime,
    duration,
    error,
    retryLoad,
    seekToPercent,
    togglePlayPause,
  };
}