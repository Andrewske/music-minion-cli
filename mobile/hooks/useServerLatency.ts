/**
 * Times a round trip to the backend's GET /health (the same lightweight
 * endpoint "Save & Test" uses). Re-measures every time the screen gains
 * focus and on demand via `refresh`.
 */
import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { healthUrl } from '../features/settings/connectionHealth';
import type { LatencyReading } from '../features/settings/connectionHealth';

const TIMEOUT_MS = 5000;

async function measure(serverUrl: string): Promise<LatencyReading> {
  const started = Date.now();
  try {
    const res = await fetch(healthUrl(serverUrl), { signal: AbortSignal.timeout(TIMEOUT_MS), cache: 'no-store' });
    if (!res.ok) return { kind: 'failed', reason: `HTTP ${res.status}` };
    return { kind: 'ok', ms: Date.now() - started };
  } catch (err) {
    return { kind: 'failed', reason: err instanceof Error ? err.message : 'Network error' };
  }
}

export function useServerLatency(serverUrl: string | null): { reading: LatencyReading; refresh: () => void } {
  const [reading, setReading] = useState<LatencyReading>({ kind: 'pending' });
  const runId = useRef(0);

  const refresh = useCallback((): void => {
    if (!serverUrl) {
      setReading({ kind: 'failed', reason: 'No server URL' });
      return;
    }
    const id = ++runId.current;
    setReading({ kind: 'pending' });
    void measure(serverUrl).then((next) => {
      if (id === runId.current) setReading(next);
    });
  }, [serverUrl]);

  useFocusEffect(refresh);
  return { reading, refresh };
}
