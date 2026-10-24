/**
 * Settings top card: connection dot (WebSocket + timed /health), the verdict,
 * the server host and the round-trip time. When something is wrong it offers
 * a Reconnect button that re-opens the WebSocket and re-times the request.
 */
import type { ReactElement } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { connectionHealth, formatLatency, serverHost } from '../../features/settings/connectionHealth';
import type { ConnectionHealth, LatencyReading } from '../../features/settings/connectionHealth';
import type { ConnectionStatus } from '../../hooks/useSyncWebSocket';

interface ConnectionCardProps {
  serverUrl: string | null;
  wsStatus: ConnectionStatus;
  reading: LatencyReading;
  onReconnect: () => void;
}

export function ConnectionCard({ serverUrl, wsStatus, reading, onReconnect }: ConnectionCardProps): ReactElement {
  const health = connectionHealth(wsStatus, reading);
  return (
    <View style={styles.card} testID="settings-connection-card">
      <View style={styles.row} accessible accessibilityLabel={describe(health, reading)}>
        <Dot color={health.color} />
        <View style={styles.text}>
          <Text style={styles.label} testID="settings-connection-label">{health.label}</Text>
          <Text style={styles.host} numberOfLines={1}>{serverUrl ? serverHost(serverUrl) : 'No server set'}</Text>
        </View>
        <View style={styles.latency}>
          <Text style={styles.ms} testID="settings-latency">{formatLatency(reading)}</Text>
          <Text style={styles.caption}>round trip</Text>
        </View>
      </View>
      {health.level !== 'good' && reading.kind !== 'pending' ? <ReconnectButton onPress={onReconnect} /> : null}
    </View>
  );
}

const describe = (health: ConnectionHealth, reading: LatencyReading): string =>
  reading.kind === 'ok' ? `${health.label}, ${formatLatency(reading)} round trip` : health.label;

function Dot({ color }: { color: string }): ReactElement {
  return (
    <View style={[styles.halo, { backgroundColor: `${color}33` }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
    </View>
  );
}

function ReconnectButton({ onPress }: { onPress: () => void }): ReactElement {
  return (
    <Pressable
      style={styles.reconnect}
      onPress={onPress}
      accessibilityRole="button"
      testID="settings-reconnect"
      android_ripple={{ color: '#7C4DFF33' }}
    >
      <Text style={styles.reconnectText}>Reconnect</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1A1A1A',
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#2E2E2E',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  halo: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  text: { flex: 1 },
  label: { color: '#E0E0E0', fontSize: 16, fontWeight: '600' },
  host: { color: '#9E9E9E', fontSize: 13, marginTop: 2 },
  latency: { alignItems: 'flex-end' },
  ms: { color: '#E0E0E0', fontSize: 26, fontWeight: '600', fontVariant: ['tabular-nums'], letterSpacing: -0.5 },
  caption: { color: '#6B6B6B', fontSize: 11 },
  reconnect: {
    marginTop: 14,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#7C4DFF',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  reconnectText: { color: '#B39DFF', fontSize: 15, fontWeight: '600' },
});
