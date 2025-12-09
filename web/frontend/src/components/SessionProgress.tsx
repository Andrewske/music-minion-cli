
interface SessionProgressProps {
  completed: number;
  target: number;
}

export function SessionProgress({ completed, target }: SessionProgressProps) {
  const percentage = Math.min((completed / target) * 100, 100);

  return (
    <div className="w-full">
      <div className="flex justify-between items-end mb-2">
        <span className="text-xs font-bold tracking-wider text-slate-400 uppercase">
          Session Progress
        </span>
        <div className="flex items-baseline gap-1">
          <span className="text-lg font-bold text-slate-200">{completed}</span>
          <span className="text-sm text-slate-500">/ {target}</span>
        </div>
      </div>

      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-indigo-500 h-full rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(99,102,241,0.5)]"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
}
