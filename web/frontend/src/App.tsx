 import { useState } from 'react';
 import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
 import { ComparisonView } from './components/ComparisonView';
 import { StatsView } from './components/StatsView';

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

function App() {
  const [currentView, setCurrentView] = useState<'compare' | 'stats'>('compare');

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950">
        {/* Sticky Navigation Header */}
        <nav className="sticky top-0 z-50 bg-slate-900 border-b border-slate-800">
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex space-x-1">
              <button
                onClick={() => setCurrentView('compare')}
                className={`px-6 py-4 text-sm font-medium transition-colors ${
                  currentView === 'compare'
                    ? 'text-slate-100 border-b-2 border-blue-500'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Compare
              </button>
              <button
                onClick={() => setCurrentView('stats')}
                className={`px-6 py-4 text-sm font-medium transition-colors ${
                  currentView === 'stats'
                    ? 'text-slate-100 border-b-2 border-blue-500'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Stats
              </button>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        {currentView === 'compare' ? <ComparisonView /> : <StatsView />}
      </div>
    </QueryClientProvider>
  );
}

export default App
