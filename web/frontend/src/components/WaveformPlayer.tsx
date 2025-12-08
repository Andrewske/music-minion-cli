import { useWavesurfer } from '../hooks/useWavesurfer';

interface WaveformPlayerProps {
  trackId: number;
  onSeek?: (progress: number) => void;
}

export function WaveformPlayer({ trackId, onSeek }: WaveformPlayerProps) {
  const { containerRef, isPlaying, currentTime, duration, error, retryLoad, togglePlayPause } = useWavesurfer({
    trackId,
    onSeek,
  });

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      {/* Error UI */}
      {error && (
        <div role="alert" aria-live="polite" className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-800 text-sm mb-2">{error}</p>
          <button
            onClick={retryLoad}
            className="text-red-600 underline text-sm hover:text-red-800 focus:ring-2 focus:ring-red-500"
          >
            Retry
          </button>
        </div>
      )}

      {/* Waveform visualization */}
      <div className="mb-4">
        {error ? (
          <div className="h-20 bg-gray-100 rounded flex items-center justify-center">
            <div className="text-gray-400 text-sm">
              Waveform unavailable
            </div>
          </div>
        ) : (
          <div ref={containerRef} />
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <button
          onClick={togglePlayPause}
          aria-label={isPlaying ? 'Pause' : 'Play'}
          className="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 touch-manipulation disabled:opacity-50 focus:ring-2 focus:ring-blue-500"
          disabled={!!error}
        >
          <span aria-hidden="true">{isPlaying ? '⏸️' : '▶️'}</span>
        </button>

        <div className="flex-1 mx-4">
          <div className="text-sm text-gray-600 text-center">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>
        </div>
      </div>
    </div>
  );
}