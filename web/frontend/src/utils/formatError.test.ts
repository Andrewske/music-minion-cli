import { describe, it, expect } from 'vitest';
import { formatError } from './formatError';

describe('formatError', () => {
  it('should return waveform-specific message for waveform errors', () => {
    const error = new Error('Failed to load waveform data');
    expect(formatError(error)).toBe('Failed to load waveform. Playing audio only.');
  });

  it('should return network error message for network failures', () => {
    const networkError = new Error('network timeout');
    expect(formatError(networkError)).toBe('Network error. Check connection and retry.');
  });

  it('should return network error message for fetch failures', () => {
    const fetchError = new Error('fetch failed');
    expect(formatError(fetchError)).toBe('Network error. Check connection and retry.');
  });

  it('should return decode error message for unsupported formats', () => {
    const decodeError = new Error('Failed to decode audio');
    expect(formatError(decodeError)).toBe('Audio format not supported by browser.');
  });

  it('should return generic message with error text for unknown errors', () => {
    const unknownError = new Error('Something unexpected happened');
    expect(formatError(unknownError)).toBe('Failed to load audio: Something unexpected happened');
  });

  it('should handle non-Error objects by converting to string', () => {
    const stringError = 'Plain string error';
    expect(formatError(stringError)).toBe('Failed to load audio: Plain string error');
  });

  it('should handle null/undefined by converting to string', () => {
    expect(formatError(null)).toBe('Failed to load audio: null');
    expect(formatError(undefined)).toBe('Failed to load audio: undefined');
  });

  it('should prioritize waveform message over other keywords', () => {
    const error = new Error('waveform network issue');
    expect(formatError(error)).toBe('Failed to load waveform. Playing audio only.');
  });

  it('should prioritize network message over decode message', () => {
    const error = new Error('network decode error');
    expect(formatError(error)).toBe('Network error. Check connection and retry.');
  });
});
