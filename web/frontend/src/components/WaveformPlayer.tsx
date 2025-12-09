import { useWavesurfer } from '../hooks/useWavesurfer';

interface WaveformPlayerProps {
  trackId: number;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
}

export function WaveformPlayer({ trackId, onSeek, isActive = false }: WaveformPlayerProps) {
  const { containerRef, isPlaying, currentTime, duration, error, retryLoad, togglePlayPause } = useWavesurfer({
    trackId,
    onSeek,
    isActive,
  });

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="relative w-full h-full flex flex-col justify-center group">
      {/* Error UI */}
      {error && (
        <div role="alert" aria-live="polite" className="absolute inset-0 z-20 bg-rose-950/90 flex flex-col items-center justify-center p-4">
          <p className="text-rose-200 text-xs mb-2 text-center">{error}</p>
          <button
            onClick={retryLoad}
            className="text-rose-400 underline text-xs hover:text-rose-300"
          >
            Retry
          </button>
        </div>
      )}

      {/* Waveform visualization */}
      <div className={`w-full h-full ${error ? 'opacity-0' : 'opacity-100'} transition-opacity`}>
        <div ref={containerRef} className="w-full h-full" />
      </div>

      {/* Hover Controls Overlay */}
      <div className="absolute inset-0 z-10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20 backdrop-blur-[1px]">
        <button
          onClick={togglePlayPause}
          className="w-12 h-12 bg-emerald-500 text-white rounded-full flex items-center justify-center hover:bg-emerald-400 shadow-lg scale-90 hover:scale-100 transition-all"
        >
          {isPlaying ? '⏸️' : '▶️'}
        </button>
      </div>

      {/* Time Display (Bottom Right) */}
      <div className="absolute bottom-1 right-2 text-[10px] font-mono text-emerald-400/80 bg-slate-900/80 px-1 rounded pointer-events-none">
        {formatTime(currentTime)} / {formatTime(duration)}
      </div>
    </div>
  );
}
