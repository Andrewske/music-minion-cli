import { describe, expect, it } from 'vitest';
import { FALLBACK_PHONE_LABEL, phoneLabel } from './deviceLabel';

describe('phoneLabel', () => {
  it('prefers the model', () => {
    expect(phoneLabel({ model: 'Pixel 9 Pro', brand: 'google' })).toBe('Pixel 9 Pro');
  });

  it('falls back to the brand', () => {
    expect(phoneLabel({ model: '  ', brand: 'samsung' })).toBe('Samsung phone');
  });

  it('falls back to a generic label', () => {
    expect(phoneLabel({})).toBe(FALLBACK_PHONE_LABEL);
  });
});
