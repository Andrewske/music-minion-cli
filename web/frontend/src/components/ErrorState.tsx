interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="text-center max-w-md p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl">
        <div className="text-6xl mb-6">😵</div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">{title}</h2>
        <p className="text-slate-400 mb-8">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-900/50"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
