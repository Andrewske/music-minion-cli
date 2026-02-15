interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      <div className="text-center max-w-md p-8 bg-obsidian-surface border border-obsidian-accent/30">
        <div className="text-6xl mb-6">😵</div>
        <h2 className="text-2xl font-bold text-white/90 mb-2">{title}</h2>
        <p className="text-white/60 font-sf-mono mb-8">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="border border-obsidian-accent/30 text-obsidian-accent px-8 py-3 text-sm tracking-wider hover:bg-obsidian-accent/10 transition-colors"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
