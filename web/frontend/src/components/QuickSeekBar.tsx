import { useEffect } from 'react';

interface QuickSeekBarProps {
  onSeek: (percent: number) => void;
  currentPercent: number;
}

export function QuickSeekBar({ onSeek, currentPercent }: QuickSeekBarProps) {
  const seekPoints = [10, 20, 30, 40, 50, 60, 70, 80, 90];

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      const num = parseInt(event.key);
      if (num >= 1 && num <= 9) {
        const percent = num * 10;
        onSeek(percent);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [onSeek]);

  return (
    <div className="flex justify-center gap-2 p-4">
      {seekPoints.map((percent) => (
        <button
          key={percent}
          onClick={() => onSeek(percent)}
          className={`w-10 h-10 rounded-full text-sm font-medium touch-manipulation ${
            Math.abs(currentPercent - percent) < 5
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          {percent / 10}
        </button>
      ))}
    </div>
  );
}