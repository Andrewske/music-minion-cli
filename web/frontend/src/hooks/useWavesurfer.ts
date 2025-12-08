import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';

interface UseWavesurferOptions {
  trackId: number;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
}

function createWavesurferConfig(container: HTMLDivElement) {
  return {
    container,
    waveColor: '#3b82f6',
    progressColor: '#1d4ed8',
    height: 80,
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

export function useWavesurfer({ trackId, onReady, onSeek }: UseWavesurferOptions) {
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

  const initWavesurfer = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      setError(null);

      // Try to load waveform first
      let waveformData = null;
      try {
        waveformData = await getWaveformData(trackId);
      } catch (waveformError) {
        // Log but don't fail - graceful degradation
        console.warn('Waveform unavailable, using basic playback:', waveformError);
      }

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

      wavesurferRef.current = wavesurfer;
    } catch (error) {
      // Audio loading failed - show error to user
      console.error('Failed to load audio:', error);
      setError(formatError(error));
    }
  }, [trackId, handleReady, handleSeek]);

  useEffect(() => {
    if (!containerRef.current || !trackId) return;

    initWavesurfer();

    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [trackId, initWavesurfer]);

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
    // Re-trigger initialization
    initWavesurfer();
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