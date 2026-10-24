/**
 * Hardware label for this phone's default device name ("Pixel 9 Pro").
 * The shared resolveDeviceName() appends the device-id suffix so two phones
 * of the same model (or a phone and an emulator) still differ.
 */

export const FALLBACK_PHONE_LABEL = 'Android Phone';

export interface HardwareInfo {
  /** Platform.constants.Model on Android, e.g. "Pixel 9 Pro". */
  model?: string;
  /** Platform.constants.Brand on Android, e.g. "google". */
  brand?: string;
}

/** Model when known, else "<Brand> phone", else "Android Phone". */
export function phoneLabel(info: HardwareInfo): string {
  const model = info.model?.trim();
  if (model) return model;
  const brand = info.brand?.trim();
  if (!brand) return FALLBACK_PHONE_LABEL;
  return `${brand.charAt(0).toUpperCase()}${brand.slice(1)} phone`;
}
