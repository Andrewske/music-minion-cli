export function WaveformSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-md p-4 animate-pulse">
      {/* Waveform placeholder */}
      <div className="h-20 bg-gray-200 rounded mb-4"></div>

      {/* Controls placeholder */}
      <div className="flex items-center justify-between">
        <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
        <div className="flex-1 mx-4">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
        </div>
      </div>
    </div>
  );
}