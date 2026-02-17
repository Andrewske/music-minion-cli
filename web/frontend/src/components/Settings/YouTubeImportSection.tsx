import { useState } from 'react';
import { ImportVideoForm } from '../YouTube/ImportVideoForm';
import { ImportPlaylistForm } from '../YouTube/ImportPlaylistForm';

type ImportMode = 'video' | 'playlist';

export function YouTubeImportSection() {
  const [mode, setMode] = useState<ImportMode>('video');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleSuccess = () => {
    // Trigger refresh of any library views
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="space-y-6">
      {/* Description */}
      <p className="text-white/60">
        Import music from YouTube videos and playlists to your library
      </p>

      {/* Mode Toggle */}
      <div className="flex gap-2 border-b border-obsidian-border">
        <button
          onClick={() => setMode('video')}
          className={`px-6 py-3 font-medium transition-colors relative ${
            mode === 'video'
              ? 'text-obsidian-accent'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Single Video
          {mode === 'video' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-obsidian-accent" />
          )}
        </button>
        <button
          onClick={() => setMode('playlist')}
          className={`px-6 py-3 font-medium transition-colors relative ${
            mode === 'playlist'
              ? 'text-obsidian-accent'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Playlist
          {mode === 'playlist' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-obsidian-accent" />
          )}
        </button>
      </div>

      {/* Form Content */}
      <div className="bg-obsidian-surface border border-obsidian-border p-6">
        {mode === 'video' ? (
          <ImportVideoForm key={`video-${refreshKey}`} onSuccess={handleSuccess} />
        ) : (
          <ImportPlaylistForm key={`playlist-${refreshKey}`} onSuccess={handleSuccess} />
        )}
      </div>

      {/* Info Box */}
      <div className="bg-obsidian-surface border border-obsidian-border p-6 space-y-3">
        <h3 className="text-lg font-semibold text-white">ℹ️ Important Notes</h3>
        <ul className="space-y-2 text-sm text-white/60">
          <li>• Downloaded videos are stored locally in ~/music/youtube/</li>
          <li>• Metadata is optional - defaults to YouTube video title and uploader</li>
          <li>• Duplicate videos are automatically detected before download</li>
          <li>• Age-restricted and private videos cannot be imported</li>
          <li>• Large playlists may take several minutes to download</li>
        </ul>
      </div>
    </div>
  );
}
