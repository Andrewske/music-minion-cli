/**
 * Handle Android Share Target — receives URLs from other apps.
 * Routes to settings screen with the shared URL pre-filled.
 *
 * expo-share-intent provides useShareIntent() hook directly.
 * We wrap it to extract URLs and handle navigation.
 */
import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { useShareIntent as useExpoShareIntent } from 'expo-share-intent';

interface ShareIntentState {
  pendingUrl: string | null;
  clearPendingUrl: () => void;
}

export const useShareIntent = (): ShareIntentState => {
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const { shareIntent, resetShareIntent } = useExpoShareIntent();

  useEffect(() => {
    if (shareIntent?.text) {
      const urlMatch = shareIntent.text.match(/https?:\/\/[^\s]+/);
      if (urlMatch) {
        setPendingUrl(urlMatch[0]);
        router.push('/(tabs)/settings');
      }
      resetShareIntent();
    }
  }, [shareIntent, resetShareIntent]);

  const clearPendingUrl = () => setPendingUrl(null);

  return { pendingUrl, clearPendingUrl };
};
