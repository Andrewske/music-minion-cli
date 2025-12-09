
interface SessionProgressProps {
  completed: number;
}

export function SessionProgress({ completed }: SessionProgressProps) {
  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-bold tracking-wider text-slate-400 uppercase">
          Session Progress
        </span>
        <span className="text-lg font-bold text-slate-200">{completed} comparisons</span>
      </div>
    </div>
  );
}
