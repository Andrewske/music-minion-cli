import { useWavesurfer } from '../hooks/useWavesurfer';

interface WaveformPlayerProps {
  trackId: number;
  onSeek?: (progress: number) => void;
  isActive?: boolean;
  onTogglePlayPause?: () => void;
  onFinish?: () => void;
}

export function WaveformPlayer({ trackId, onSeek, isActive = false, onTogglePlayPause, onFinish }: WaveformPlayerProps) {
  const { containerRef, isPlaying, currentTime, duration, error, retryLoad, togglePlayPause } = useWavesurfer({
    trackId,
    onSeek,
    isActive,
    onFinish,
  });

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center w-full h-full">
      {/* Play/Pause Button (Left Side) */}
      <button
        onClick={onTogglePlayPause || togglePlayPause}
        className="flex-shrink-0 w-10 h-10 ml-3 mr-2 bg-emerald-500 text-white rounded-full flex items-center justify-center hover:bg-emerald-400 shadow-lg transition-colors"
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 ml-0.5">
            <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
          </svg>
        )}
      </button>

      <div className="relative flex-1 h-full flex flex-col justify-center min-w-0">
        {/* Error UI */}
        {error && (
          <div role="alert" aria-live="polite" className="absolute inset-0 z-20 bg-rose-950/90 flex flex-col items-center justify-center p-2 rounded-r-lg">
            <p className="text-rose-200 text-xs mb-1 text-center truncate w-full px-2">{error}</p>
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

        {/* Time Display (Bottom Right) */}
        <div className="absolute bottom-1 right-2 z-10 text-[10px] font-mono text-emerald-400/80 bg-slate-900/80 px-1 rounded pointer-events-none">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>
    </div>
  );
}
