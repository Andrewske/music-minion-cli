import { useState } from 'react';

interface ImportTrackFormProps {
  onSuccess: () => void;
}

interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: {
    id: number;
    title: string;
    artist: string | null;
    soundcloud_id: string;
    source_url: string;
    duration: number;
  };
  error?: string;
}

export function ImportTrackForm({ onSuccess }: ImportTrackFormProps) {
  const [url, setUrl] = useState('');
  const [artist, setArtist] = useState('');
  const [title, setTitle] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const pollJobStatus = async (jobId: string): Promise<JobStatus> => {
    const MAX_POLLS = 300; // 5 minutes max (300 * 1 second)
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

      // Poll every 1 second
      await new Promise((resolve) => setTimeout(resolve, 1000));
      polls++;
    }

    throw new Error('Import timed out after 5 minutes. The job may still be running in the background.');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setIsLoading(true);

    try {
      // Start import job
      const startResponse = await fetch('/api/soundcloud/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          artist: artist || null,
          title: title || null,
        }),
      });

      if (!startResponse.ok) {
        const errorData = await startResponse.json();
        throw new Error(errorData.detail || 'Failed to start import');
      }

      const { job_id } = await startResponse.json();

      // Poll for completion
      const result = await pollJobStatus(job_id);

      // Success!
      if (result.result) {
        setSuccessMessage(
          `Imported: ${result.result.artist || 'Unknown Artist'} - ${result.result.title}`
        );
        // Clear form
        setUrl('');
        setArtist('');
        setTitle('');
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Info Banner */}
      <div className="p-3 bg-orange-900/20 border border-orange-500/20 rounded-lg text-orange-300 text-sm">
        Tracks are streamed from SoundCloud, not downloaded locally.
      </div>

      {/* URL Field */}
      <div>
        <label htmlFor="url" className="block text-sm font-medium text-slate-300 mb-2">
          SoundCloud URL <span className="text-red-500">*</span>
        </label>
        <input
          id="url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://soundcloud.com/artist/track-name"
          required
          disabled={isLoading}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {/* Artist Field */}
      <div>
        <label htmlFor="artist" className="block text-sm font-medium text-slate-300 mb-2">
          Artist <span className="text-xs text-slate-500">(optional, defaults to uploader)</span>
        </label>
        <input
          id="artist"
          type="text"
          value={artist}
          onChange={(e) => setArtist(e.target.value)}
          placeholder="Artist name"
          disabled={isLoading}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {/* Title Field */}
      <div>
        <label htmlFor="title" className="block text-sm font-medium text-slate-300 mb-2">
          Title <span className="text-xs text-slate-500">(optional, defaults to track title)</span>
        </label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Track title"
          disabled={isLoading}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isLoading || !url}
        className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
      >
        {isLoading ? (
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
            <span>Importing...</span>
          </>
        ) : (
          'Import Track'
        )}
      </button>

      {/* Success Message */}
      {successMessage && (
        <div className="p-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg text-emerald-400 text-sm">
          {successMessage}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-900/20 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}
    </form>
  );
}
