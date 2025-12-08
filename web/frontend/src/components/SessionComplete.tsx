interface SessionCompleteProps {
  completed: number;
  onStartNew: () => void;
}

export function SessionComplete({ completed, onStartNew }: SessionCompleteProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-4">🎉</div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Session Complete!
        </h1>
        <p className="text-gray-600 mb-6">
          You completed {completed} track comparisons. Great job!
        </p>
        <button
          onClick={onStartNew}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 touch-manipulation"
        >
          Start New Session
        </button>
      </div>
    </div>
  );
}