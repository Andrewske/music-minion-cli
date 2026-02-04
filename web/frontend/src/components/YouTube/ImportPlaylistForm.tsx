import { useState } from 'react';
import { ProgressBar, type FailureInfo } from './ProgressBar';

interface ImportPlaylistFormProps {
  onSuccess: () => void;
}

interface PlaylistPreview {
  title: string;
  video_count: number;
  videos: Array<{ id: string; title: string; duration: number }>;
}

interface ImportedTrack {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  youtube_id: string;
  local_path: string;
  duration: number;
}

interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  current_step?: 'downloading' | 'processing' | null;
  current_item?: number | null;
  total_items?: number | null;
  failures?: FailureInfo[];
  result?: {
    imported_count: number;
    skipped_count: number;
    failed_count: number;
    failures: Array<{ video_id: string; error: string }>;
    tracks: Array<ImportedTrack>;
  };
  error?: string;
}

export function ImportPlaylistForm({ onSuccess }: ImportPlaylistFormProps) {
  const [playlistInput, setPlaylistInput] = useState('');
  const [preview, setPreview] = useState<PlaylistPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobStatus['result'] | null>(null);

  const extractPlaylistId = (input: string): string => {
    // Try to extract playlist ID from URL
    const match = input.match(/list=([a-zA-Z0-9_-]+)/);
    return match ? match[1] : input;
  };

  const fetchPreview = async () => {
    setError(null);
    setPreview(null);
    setIsLoadingPreview(true);

    try {
      const playlistId = extractPlaylistId(playlistInput);
      const response = await fetch(`/api/youtube/playlist/${playlistId}`);

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
      const response = await fetch(`/api/youtube/import/${jobId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch job status');
      }

      const status: JobStatus = await response.json();

      // Update progress state for UI
      setJobStatus(status);

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
    setJobStatus(null);
    setIsImporting(true);

    try {
      const playlistId = extractPlaylistId(playlistInput);

      // Start import job
      const startResponse = await fetch('/api/youtube/import-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ playlist_id: playlistId }),
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
      {/* Input Field */}
      <div>
        <label htmlFor="playlist" className="block text-sm font-medium text-slate-300 mb-2">
          Playlist ID or URL <span className="text-red-500">*</span>
        </label>
        <div className="flex gap-2">
          <input
            id="playlist"
            type="text"
            value={playlistInput}
            onChange={(e) => setPlaylistInput(e.target.value)}
            placeholder="PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf or full URL"
            disabled={isLoadingPreview || isImporting}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={fetchPreview}
            disabled={!playlistInput || isLoadingPreview || isImporting}
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
            {preview.video_count} video{preview.video_count !== 1 ? 's' : ''} in playlist
          </p>
        </div>
      )}

      {/* Import Button or Progress Bar */}
      {preview && (
        isImporting && jobStatus ? (
          <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-lg">
            <ProgressBar
              progress={jobStatus.progress ?? 0}
              currentStep={jobStatus.current_step}
              currentItem={jobStatus.current_item}
              totalItems={jobStatus.total_items}
              failures={jobStatus.failures}
            />
          </div>
        ) : (
          <button
            type="button"
            onClick={handleImport}
            disabled={isImporting}
            className="w-full px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
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
                <span>Starting...</span>
              </>
            ) : (
              'Import Playlist'
            )}
          </button>
        )
      )}

      {/* Result */}
      {result && (
        <div className="p-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg space-y-2">
          <div className="text-emerald-400 font-medium">✓ Playlist import complete!</div>
          <div className="text-sm text-slate-300 space-y-1">
            <div>Imported: {result.imported_count} tracks</div>
            <div>Skipped: {result.skipped_count} duplicates</div>
            {result.failed_count > 0 && (
              <div className="text-red-400">
                Failed: {result.failed_count} videos
                {result.failures.length > 0 && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer hover:text-red-300">
                      Show failures ({result.failures.length})
                    </summary>
                    <ul className="mt-2 space-y-1 pl-4">
                      {result.failures.slice(0, 5).map((failure, idx) => (
                        <li key={idx}>
                          {failure.video_id}: {failure.error}
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
          ❌ {error}
        </div>
      )}
    </div>
  );
}
