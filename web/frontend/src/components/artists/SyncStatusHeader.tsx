import type { ReactElement } from 'react';
import { CheckCircle2, AlertCircle, Loader2, Circle, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { useFeedSyncStatus, useFeedSync } from '../../hooks/useArtists';

function formatRelativeTime(isoStr: unknown): string {
  if (typeof isoStr !== 'string') return 'unknown';
  const date = new Date(isoStr);
  if (isNaN(date.getTime())) return 'unknown';
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

interface StatusIconProps {
  status: unknown;
}

function StatusIcon({ status }: StatusIconProps): ReactElement {
  if (status === 'running') return <Loader2 className="w-3.5 h-3.5 animate-spin text-obsidian-accent" />;
  if (status === 'error') return <AlertCircle className="w-3.5 h-3.5 text-amber-400" />;
  if (status === 'ok') return <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />;
  return <Circle className="w-3.5 h-3.5 text-white/30" />;
}

export function SyncStatusHeader(): ReactElement {
  const { data } = useFeedSyncStatus();
  const syncMut = useFeedSync();

  const status = data?.last_run_status;
  const lastRunAt = data?.last_run_at;
  const eventsAdded = data?.events_added_last_run;
  const lastError = typeof data?.last_error === 'string' ? data.last_error : null;
  const isRunning = syncMut.isPending || status === 'running';

  const neverRun = data !== undefined && !lastRunAt;

  return (
    <div className="mb-4 border border-obsidian-border bg-obsidian-surface/50 px-4 py-2.5">
      <div className="flex items-center gap-2">
        <StatusIcon status={status} />

        <span className="font-sf-mono text-xs text-white/60 flex-1">
          {neverRun
            ? 'Feed sync never run'
            : (
              <>
                Feed sync:&nbsp;
                <span className="text-white/80">{String(status ?? '—')}</span>
                {lastRunAt != null && (
                  <> · last run <span className="text-white/80">{formatRelativeTime(lastRunAt)}</span></>
                )}
                {eventsAdded != null && typeof eventsAdded === 'number' && eventsAdded > 0 && (
                  <> · <span className="text-obsidian-accent">{eventsAdded} new events</span></>
                )}
              </>
            )
          }
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={() => syncMut.mutate()}
          disabled={isRunning}
          className="gap-1.5 font-sf-mono text-xs shrink-0"
        >
          <RefreshCw className={`w-3 h-3 ${syncMut.isPending ? 'animate-spin' : ''}`} />
          Sync now
        </Button>
      </div>

      {lastError !== null && (
        <p className="mt-1 font-sf-mono text-xs text-red-400 truncate">{lastError}</p>
      )}
    </div>
  );
}
