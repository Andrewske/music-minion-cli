import { useState, useEffect, useRef } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { ComparisonView } from './components/ComparisonView';
import { RadioPage } from './components/RadioPage';
import { HistoryPage } from './components/HistoryPage';
import { YouTubeImport } from './components/YouTube/YouTubeImport';
import { useRadioStore } from './stores/radioStore';
import { getNowPlaying } from './api/radio';
import type { NowPlaying } from './api/radio';

type View = 'radio' | 'comparison' | 'history' | 'youtube';

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

function AppContent(): JSX.Element {
  const [view, setView] = useState<View>('radio');
  const { isMuted, setNowPlaying, toggleMute, nowPlaying } = useRadioStore();
  const audioRef = useRef<HTMLAudioElement>(null);

  // Poll now-playing data (moved from RadioPlayer)
  const { data: nowPlayingData } = useQuery<NowPlaying>({
    queryKey: ['nowPlaying'],
    queryFn: getNowPlaying,
    refetchInterval: 5000,
    retry: 1,
  });

  // Sync poll results to store
  useEffect(() => {
    setNowPlaying(nowPlayingData ?? null);
  }, [nowPlayingData, setNowPlaying]);

  // Start playing when component mounts (muted initially)
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.play().catch(() => {
        // Autoplay blocked - user will need to click to start
      });
    }
  }, []);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Global audio element - never unmounts */}
      <audio
        ref={audioRef}
        src="/api/radio/stream"
        muted={isMuted}
        onError={(e) => console.error('Audio error:', e)}
      />

      {/* Navigation */}
      <nav className="border-b border-slate-800 px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <NavButton active={view === 'radio'} onClick={() => setView('radio')}>
              Radio
            </NavButton>
            <NavButton active={view === 'history'} onClick={() => setView('history')}>
              History
            </NavButton>
            <NavButton active={view === 'comparison'} onClick={() => setView('comparison')}>
              Ranking
            </NavButton>
            <NavButton active={view === 'youtube'} onClick={() => setView('youtube')}>
              YouTube
            </NavButton>
          </div>

          {/* Radio mini-display */}
          {nowPlaying && (
            <div className="flex items-center gap-3">
              <button
                onClick={toggleMute}
                className="text-slate-400 hover:text-white transition-colors"
                aria-label={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted ? (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                  </svg>
                )}
              </button>
              <button
                onClick={() => setView('radio')}
                className={
                  'flex items-center gap-2 text-sm hover:text-white transition-colors ' +
                  (isMuted ? 'text-slate-500' : 'text-slate-300')
                }
              >
                <span className="max-w-[200px] truncate">
                  {nowPlaying.track.artist} - {nowPlaying.track.title}
                </span>
                <span className="text-xs text-slate-500">• {nowPlaying.station_name}</span>
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* Content */}
      {view === 'radio' ? (
        <RadioPage />
      ) : view === 'history' ? (
        <HistoryPage />
      ) : view === 'youtube' ? (
        <YouTubeImport />
      ) : (
        <ComparisonView />
      )}
    </div>
  );
}

function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
