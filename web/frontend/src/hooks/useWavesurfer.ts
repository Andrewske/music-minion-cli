import { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';

interface UseWavesurferOptions {
  trackId: number;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
}

export function useWavesurfer({ trackId, onReady, onSeek }: UseWavesurferOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    if (!containerRef.current || !trackId) return;

    const initWavesurfer = async () => {
      try {
        // Get waveform data
        const waveformData = await getWaveformData(trackId);

        // Create WaveSurfer instance
        const wavesurfer = WaveSurfer.create({
          container: containerRef.current!,
          waveColor: '#3b82f6',
          progressColor: '#1d4ed8',
          height: 80,
          normalize: true,
          backend: 'MediaElement',
        });

        // Load audio and waveform data
        wavesurfer.load(getStreamUrl(trackId), [waveformData.peaks]);

        // Set up event listeners
        wavesurfer.on('ready', () => {
          setDuration(wavesurfer.getDuration());
          onReady?.(wavesurfer.getDuration());
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
          onSeek?.(progress);
        });

        wavesurferRef.current = wavesurfer;
      } catch (error) {
        console.error('Failed to initialize WaveSurfer:', error);
      }
    };

    initWavesurfer();

    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [trackId, onReady, onSeek]);

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

  return {
    containerRef,
    isPlaying,
    currentTime,
    duration,
    seekToPercent,
    togglePlayPause,
  };
}