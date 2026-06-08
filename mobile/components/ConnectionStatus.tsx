/**
 * Connection-status indicator for the WebSocket sync hook.
 *
 * Presentational/self-contained: pass the `status` and `retry` returned by
 * useSyncWebSocket. Renders a small pill banner while connecting/offline,
 * a manual-retry button when offline, and fires a brief "restored" toast
 * when the socket comes back after being offline.
 *
 * Mount once near the root, alongside the existing useSyncWebSocket call.
 * Renders nothing while connected (no chrome when healthy).
 */
import { useEffect, useRef, type ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import Toast from 'react-native-toast-message';
import type { ConnectionStatus as Status } from '../hooks/useSyncWebSocket';

interface ConnectionStatusProps {
  status: Status;
  retry: () => void;
}

const LABELS: Record<Status, string> = {
  connected: 'Connected',
  connecting: 'Reconnecting…',
  offline: 'Offline',
};

const DOT_COLORS: Record<Status, string> = {
  connected: '#4CAF50',
  connecting: '#FFB300',
  offline: '#E53935',
};

export function ConnectionStatus({ status, retry }: ConnectionStatusProps): ReactElement | null {
  const wasOfflineRef = useRef(false);

  // Fire a brief toast when the connection is restored after being offline.
  useEffect(() => {
    if (status === 'offline' || status === 'connecting') {
      wasOfflineRef.current = true;
    } else if (status === 'connected' && wasOfflineRef.current) {
      wasOfflineRef.current = false;
      Toast.show({
        type: 'success',
        text1: 'Connection restored',
        visibilityTime: 2000,
      });
    }
  }, [status]);

  if (status === 'connected') {
    return null;
  }

  return (
    <View style={styles.banner}>
      <View style={[styles.dot, { backgroundColor: DOT_COLORS[status] }]} />
      <Text style={styles.label}>{LABELS[status]}</Text>
      {status === 'offline' && (
        <Pressable style={styles.retryBtn} onPress={retry} hitSlop={8}>
          <Text style={styles.retryText}>Retry</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1A1A1A',
    borderTopWidth: 1,
    borderTopColor: '#333',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  label: {
    flex: 1,
    color: '#E0E0E0',
    fontSize: 13,
    fontWeight: '600',
  },
  retryBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#7C4DFF',
  },
  retryText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
});
