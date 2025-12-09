import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';

interface UseWavesurferOptions {
  trackId: number;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
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

function formatError(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error);

  if (msg.includes('waveform')) {
    return 'Failed to load waveform. Playing audio only.';
  }
  if (msg.includes('network') || msg.includes('fetch')) {
    return 'Network error. Check connection and retry.';
  }
  if (msg.includes('decode')) {
    return 'Audio format not supported by browser.';
  }
  return `Failed to load audio: ${msg}`;
}

export function useWavesurfer({ trackId, onReady, onSeek, isActive = false }: UseWavesurferOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleReady = useCallback((duration: number) => {
    setDuration(duration);
    onReady?.(duration);
  }, [onReady]);

  const handleSeek = useCallback((progress: number) => {
    onSeek?.(progress);
  }, [onSeek]);

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
      } catch (waveformError) {
        // Log but don't fail - graceful degradation
        console.warn('Waveform unavailable, using basic playback:', waveformError);
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

        // Autoplay if this track is active
        if (isActive) {
          try {
            wavesurfer.play();
          } catch (err) {
            console.warn('Autoplay blocked:', err);
          }
        }
      });

      wavesurfer.on('error', (error) => {
        console.error('WaveSurfer error:', error);
        setError(formatError(error));
      });

      wavesurfer.on('play', () => setIsPlaying(true));
      wavesurfer.on('pause', () => setIsPlaying(false));
      wavesurfer.on('finish', () => setIsPlaying(false));

      wavesurfer.on('audioprocess', () => {
        setCurrentTime(wavesurfer.getCurrentTime());
      });

      wavesurfer.on('interaction', () => {
        setCurrentTime(wavesurfer.getCurrentTime());
        const progress = wavesurfer.getCurrentTime() / wavesurfer.getDuration();
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
      console.error('Failed to load audio:', error);
      setError(formatError(error));
    }
  }, [trackId, handleReady, handleSeek]);

  useEffect(() => {
    if (!containerRef.current || !trackId) return;

    // AbortController to cancel async operations on cleanup
    const abortController = new AbortController();

    console.log('[useWavesurfer] Effect triggered for track:', trackId, 'existing instance:', !!wavesurferRef.current);
    initWavesurfer(abortController.signal);

    return () => {
      console.log('[useWavesurfer] Cleanup for track:', trackId);
      // Abort any in-flight async operations
      abortController.abort();

      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [trackId, initWavesurfer]);

  // Watch for isActive changes to pause/play accordingly
  const prevIsActive = useRef(isActive);

  useEffect(() => {
    if (!wavesurferRef.current) return;

    if (isActive && !prevIsActive.current) {
      // Became active - seek to start and play
      wavesurferRef.current.seekTo(0);
      try {
        wavesurferRef.current.play();
      } catch (err) {
        console.warn('Play failed:', err);
      }
    } else if (!isActive && prevIsActive.current) {
      // Became inactive - pause
      if (wavesurferRef.current.isPlaying()) {
        wavesurferRef.current.pause();
      }
    }

    prevIsActive.current = isActive;
  }, [isActive]);

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
    initWavesurfer(abortController.signal);
  }, [initWavesurfer]);

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