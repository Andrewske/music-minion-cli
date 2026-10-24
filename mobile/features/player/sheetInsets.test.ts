import { describe, expect, it } from 'vitest';
import { fullPlayerInsets } from './sheetInsets';

describe('fullPlayerInsets', () => {
  it('pads by both system bars on Android', () => {
    // Pixel 9 Pro: 153px status bar at 360dpi (scale 2.25) → 68dp
    expect(fullPlayerInsets('android', { top: 68, bottom: 24 })).toEqual({ top: 68, bottom: 24 });
  });

  it('skips the top inset on iOS (pageSheet sits below the status bar)', () => {
    expect(fullPlayerInsets('ios', { top: 59, bottom: 34 })).toEqual({ top: 0, bottom: 34 });
  });
});
