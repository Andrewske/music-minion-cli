import { describe, expect, it } from 'vitest';
import { CONNECTION_DOT_COLORS, connectionLabel } from './connectionDot';

describe('connectionLabel', () => {
  it('speaks the row label and the server state', () => {
    expect(connectionLabel('Settings', 'connected')).toBe('Settings, server connected');
    expect(connectionLabel('Settings', 'connecting')).toBe('Settings, server reconnecting');
    expect(connectionLabel('Settings', 'offline')).toBe('Settings, server offline');
  });

  it('has a distinct colour per state', () => {
    expect(new Set(Object.values(CONNECTION_DOT_COLORS)).size).toBe(3);
  });
});
