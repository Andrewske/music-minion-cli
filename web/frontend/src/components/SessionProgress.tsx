

interface SessionProgressProps {
  completed: number;
  target: number;
}

export function SessionProgress({ completed, target }: SessionProgressProps) {
  const percentage = Math.min((completed / target) * 100, 100);

  return (
    <div className="w-full px-4 py-2">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-gray-700">
          {completed} / {target} comparisons
        </span>
        <span className="text-sm text-gray-500">
          {percentage.toFixed(0)}%
        </span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
}