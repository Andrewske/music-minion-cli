/**
 * Consume the share intent from the root ShareIntentProvider context.
 *
 * Navigation to this screen is handled in app/_layout.tsx (where the provider
 * is always mounted, so cold-start share intents work). This hook only extracts
 * the shared URL and exposes it, resetting the intent once consumed.
 */
import { useEffect, useState } from 'react';
import { useShareIntentContext } from 'expo-share-intent';

interface ShareIntentState {
  pendingUrl: string | null;
  clearPendingUrl: () => void;
}

export const useShareIntent = (): ShareIntentState => {
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntentContext();

  useEffect(() => {
    if (!hasShareIntent) return;
    const candidate = shareIntent.webUrl ?? shareIntent.text ?? null;
    const urlMatch = candidate?.match(/https?:\/\/[^\s]+/);
    if (urlMatch) {
      setPendingUrl(urlMatch[0]);
    }
    resetShareIntent();
  }, [hasShareIntent, shareIntent, resetShareIntent]);

  const clearPendingUrl = (): void => setPendingUrl(null);

  return { pendingUrl, clearPendingUrl };
};
