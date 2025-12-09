interface SessionCompleteProps {
  completed: number;
  onStartNew: () => void;
}

export function SessionComplete({ completed, onStartNew }: SessionCompleteProps) {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="text-center max-w-md p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl">
        <div className="text-6xl mb-6 animate-bounce">🎉</div>
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-500 mb-2">
          Session Complete!
        </h1>
        <p className="text-slate-400 mb-8 text-lg">
          You completed <span className="font-bold text-slate-200">{completed}</span> track comparisons.
        </p>
        <button
          onClick={onStartNew}
          className="w-full bg-emerald-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-900/50"
        >
          Start New Session
        </button>
      </div>
    </div>
  );
}
