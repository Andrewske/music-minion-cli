import { getDefaultApiClient } from './client';

export interface DiscoverySyncJob {
  job_id: string;
}

export interface DiscoverySyncStatus {
  status: 'running' | 'completed' | 'failed';
  progress_message: string | null;
  progress_current: number;
  progress_total: number;
  result: {
    tracks_fetched: number;
    tracks_new: number;
    tracks_added_to_playlist: number;
    mixes_added: number;
    artists_checked: number;
    errors: string[];
    dry_run: boolean;
  } | null;
  error: string | null;
}

export interface LastSync {
  id: number;
  started_at: string;
  completed_at: string | null;
  artists_checked: number;
  tracks_fetched: number;
  tracks_added: number;
  mixes_added: number;
  tracks_skipped: number;
  dry_run: boolean;
  duration_seconds: number | null;
}

const discoveryBase = (): string => `${getDefaultApiClient().getBaseUrl()}/discovery`;

export async function triggerDiscoverySync(dryRun: boolean = false): Promise<DiscoverySyncJob> {
  const response = await fetch(`${discoveryBase()}/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    try {
      const error = JSON.parse(errorText);
      throw new Error(error.detail || 'Failed to trigger discovery sync');
    } catch {
      throw new Error(`Failed to trigger discovery sync: ${response.status} ${errorText.substring(0, 100)}`);
    }
  }

  return response.json();
}

export async function getDiscoverySyncStatus(jobId: string): Promise<DiscoverySyncStatus> {
  return getDefaultApiClient().request<DiscoverySyncStatus>(`/discovery/sync/status/${jobId}`);
}

export async function getLastSync(): Promise<LastSync | null> {
  return getDefaultApiClient().request<LastSync | null>('/discovery/last-sync');
}

export async function seedArtists(
  csvPath?: string
): Promise<{ artists_imported: number; resolution_started: boolean }> {
  const response = await fetch(`${discoveryBase()}/seed-artists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: csvPath ? JSON.stringify({ csv_path: csvPath }) : undefined,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to seed artists');
  }

  return response.json();
}
