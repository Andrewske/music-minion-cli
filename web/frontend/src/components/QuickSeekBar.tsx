import { useEffect, useRef } from 'react';

interface QuickSeekBarProps {
  onSeek: (percent: number) => void;
  currentPercent: number;
  className?: string;
}

export function QuickSeekBar({ onSeek, currentPercent, className = '' }: QuickSeekBarProps) {
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // Only trigger if no input is focused
      if (['INPUT', 'TEXTAREA'].includes((event.target as HTMLElement).tagName)) return;
      
      const num = parseInt(event.key);
      if (num >= 0 && num <= 9) {
        // 0 = 0%, 1-9 = 10-90%
        const percent = num === 0 ? 0 : num * 10;
        onSeek(percent);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [onSeek]);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!barRef.current) return;
    const rect = barRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = Math.min(Math.max((x / rect.width) * 100, 0), 100);
    onSeek(percent);
  };

  return (
    <div 
      className={`group relative cursor-pointer py-2 touch-none ${className}`}
      onClick={handleClick}
      ref={barRef}
    >
      {/* Background Track */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 bg-slate-800 rounded-full overflow-hidden group-hover:h-2 transition-all">
        {/* Progress Fill */}
        <div 
          className="h-full bg-emerald-500 transition-all duration-100 ease-out"
          style={{ width: `${currentPercent}%` }}
        />
      </div>
      
      {/* Hover Thumb (Optional visual cue) */}
      <div 
        className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
        style={{ left: `${currentPercent}%`, transform: 'translate(-50%, -50%)' }}
      />
    </div>
  );
}
