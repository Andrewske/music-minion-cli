import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ComparisonView } from './components/ComparisonView';
import { RadioPage } from './components/RadioPage';

type View = 'radio' | 'comparison';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
    mutations: {
      retry: 1,
    },
  },
});

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      className={
        'px-4 py-2 text-sm font-medium rounded-lg transition-colors ' +
        (active
          ? 'bg-emerald-600 text-white'
          : 'text-slate-400 hover:text-white hover:bg-slate-800')
      }
    >
      {children}
    </button>
  );
}

function App(): JSX.Element {
  const [view, setView] = useState<View>('radio');

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950">
        {/* Navigation */}
        <nav className="border-b border-slate-800 px-6 py-3">
          <div className="flex items-center gap-2">
            <NavButton active={view === 'radio'} onClick={() => setView('radio')}>
              Radio
            </NavButton>
            <NavButton active={view === 'comparison'} onClick={() => setView('comparison')}>
              Ranking
            </NavButton>
          </div>
        </nav>

        {/* Content */}
        {view === 'radio' ? <RadioPage /> : <ComparisonView />}
      </div>
    </QueryClientProvider>
  );
}

export default App;
