import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ComparisonView } from './components/ComparisonView';
import { PlaylistBuilder } from './pages/PlaylistBuilder';

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
  // Simple hash-based routing (install react-router-dom for proper routing)
  const isBuilderView = window.location.hash === '#/playlist-builder';

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950">
        {isBuilderView ? <PlaylistBuilder /> : <ComparisonView />}
      </div>
    </QueryClientProvider>
  );
}

export default App
