import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ComparisonView } from './components/ComparisonView';

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
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950">
        <ComparisonView />
      </div>
    </QueryClientProvider>
  );
}

export default App
