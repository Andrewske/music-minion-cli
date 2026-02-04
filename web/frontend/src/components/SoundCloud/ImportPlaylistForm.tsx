import { useState } from 'react';

interface ImportPlaylistFormProps {
  onSuccess: () => void;
}

interface PlaylistPreview {
  title: string;
  track_count: number;
  tracks: Array<{ id: string; title: string; duration: number }>;
}

interface ImportedTrack {
  id: number;
  title: string;
  artist: string | null;
  soundcloud_id: string;
  source_url: string;
  duration: number;
}

interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: {
    imported_count: number;
    skipped_count: number;
    failed_count: number;
    failures: Array<{ track_url: string; error: string }>;
    tracks: Array<ImportedTrack>;
  };
  error?: string;
}

export function ImportPlaylistForm({ onSuccess }: ImportPlaylistFormProps) {
  const [playlistUrl, setPlaylistUrl] = useState('');
  const [preview, setPreview] = useState<PlaylistPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobStatus['result'] | null>(null);

  const fetchPreview = async () => {
    setError(null);
    setPreview(null);
    setIsLoadingPreview(true);

    try {
      const response = await fetch(
        `/api/soundcloud/playlist-preview?url=${encodeURIComponent(playlistUrl)}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch playlist');
      }

      const data: PlaylistPreview = await response.json();
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch playlist preview');
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const pollJobStatus = async (jobId: string): Promise<JobStatus> => {
    const MAX_POLLS = 900; // 30 minutes max (900 * 2 seconds) - playlists can be large
    let polls = 0;

    while (polls < MAX_POLLS) {
      const response = await fetch(`/api/soundcloud/import/${jobId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch job status');
      }

      const status: JobStatus = await response.json();

      if (status.status === 'completed') {
        return status;
      } else if (status.status === 'failed') {
        throw new Error(status.error || 'Import failed');
      }

      // Poll every 2 seconds (playlist imports take longer)
      await new Promise((resolve) => setTimeout(resolve, 2000));
      polls++;
    }

    throw new Error('Import timed out after 30 minutes. The job may still be running in the background.');
  };

  const handleImport = async () => {
    setError(null);
    setResult(null);
    setIsImporting(true);

    try {
      // Start import job
      const startResponse = await fetch('/api/soundcloud/import-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ playlist_url: playlistUrl }),
      });

      if (!startResponse.ok) {
        const errorData = await startResponse.json();
        throw new Error(errorData.detail || 'Failed to start import');
      }

      const { job_id } = await startResponse.json();

      // Poll for completion
      const jobResult = await pollJobStatus(job_id);

      // Success!
      if (jobResult.result) {
        setResult(jobResult.result);
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Info Banner */}
      <div className="p-3 bg-orange-900/20 border border-orange-500/20 rounded-lg text-orange-300 text-sm">
        Tracks are streamed from SoundCloud, not downloaded locally.
      </div>

      {/* Input Field */}
      <div>
        <label htmlFor="playlist" className="block text-sm font-medium text-slate-300 mb-2">
          Playlist URL <span className="text-red-500">*</span>
        </label>
        <div className="flex gap-2">
          <input
            id="playlist"
            type="url"
            value={playlistUrl}
            onChange={(e) => setPlaylistUrl(e.target.value)}
            placeholder="https://soundcloud.com/artist/sets/playlist-name"
            disabled={isLoadingPreview || isImporting}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={fetchPreview}
            disabled={!playlistUrl || isLoadingPreview || isImporting}
            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors duration-200"
          >
            {isLoadingPreview ? 'Loading...' : 'Preview'}
          </button>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
          <h3 className="text-lg font-semibold text-white mb-2">{preview.title}</h3>
          <p className="text-slate-400 text-sm">
            {preview.track_count} track{preview.track_count !== 1 ? 's' : ''} in playlist
          </p>
        </div>
      )}

      {/* Import Button */}
      {preview && (
        <button
          type="button"
          onClick={handleImport}
          disabled={isImporting}
          className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
        >
          {isImporting ? (
            <>
              <svg
                className="animate-spin h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              <span>Importing Playlist...</span>
            </>
          ) : (
            'Import Playlist'
          )}
        </button>
      )}

      {/* Result */}
      {result && (
        <div className="p-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg space-y-2">
          <div className="text-emerald-400 font-medium">Playlist import complete!</div>
          <div className="text-sm text-slate-300 space-y-1">
            <div>Imported: {result.imported_count} tracks</div>
            <div>Skipped: {result.skipped_count} duplicates</div>
            {result.failed_count > 0 && (
              <div className="text-red-400">
                Failed: {result.failed_count} tracks
                {result.failures.length > 0 && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer hover:text-red-300">
                      Show failures ({result.failures.length})
                    </summary>
                    <ul className="mt-2 space-y-1 pl-4">
                      {result.failures.slice(0, 5).map((failure, idx) => (
                        <li key={idx}>
                          {failure.track_url}: {failure.error}
                        </li>
                      ))}
                      {result.failures.length > 5 && (
                        <li>... and {result.failures.length - 5} more</li>
                      )}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-900/20 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
