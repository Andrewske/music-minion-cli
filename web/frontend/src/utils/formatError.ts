export function formatError(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error);

  if (msg.includes('waveform')) {
    return 'Failed to load waveform. Playing audio only.';
  }
  if (msg.includes('network') || msg.includes('fetch')) {
    return 'Network error. Check connection and retry.';
  }
  if (msg.includes('decode')) {
    return 'Audio format not supported by browser.';
  }
  return `Failed to load audio: ${msg}`;
}
