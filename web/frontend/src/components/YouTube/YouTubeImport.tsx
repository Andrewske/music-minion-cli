import { useState } from 'react';
import { ImportVideoForm } from './ImportVideoForm';
import { ImportPlaylistForm } from './ImportPlaylistForm';

type ImportMode = 'video' | 'playlist';

export function YouTubeImport() {
  const [mode, setMode] = useState<ImportMode>('video');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleSuccess = () => {
    // Trigger refresh of any library views
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">YouTube Import</h1>
          <p className="text-slate-400">
            Import music from YouTube videos and playlists to your library
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="flex gap-2 border-b border-slate-800">
          <button
            onClick={() => setMode('video')}
            className={`px-6 py-3 font-medium transition-colors relative ${
              mode === 'video'
                ? 'text-emerald-400'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Single Video
            {mode === 'video' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />
            )}
          </button>
          <button
            onClick={() => setMode('playlist')}
            className={`px-6 py-3 font-medium transition-colors relative ${
              mode === 'playlist'
                ? 'text-emerald-400'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Playlist
            {mode === 'playlist' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />
            )}
          </button>
        </div>

        {/* Form Content */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          {mode === 'video' ? (
            <ImportVideoForm key={`video-${refreshKey}`} onSuccess={handleSuccess} />
          ) : (
            <ImportPlaylistForm key={`playlist-${refreshKey}`} onSuccess={handleSuccess} />
          )}
        </div>

        {/* Info Box */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-3">
          <h3 className="text-lg font-semibold text-white">ℹ️ Important Notes</h3>
          <ul className="space-y-2 text-sm text-slate-400">
            <li>• Downloaded videos are stored locally in ~/music/youtube/</li>
            <li>• Metadata is optional - defaults to YouTube video title and uploader</li>
            <li>• Duplicate videos are automatically detected before download</li>
            <li>• Age-restricted and private videos cannot be imported</li>
            <li>• Large playlists may take several minutes to download</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
