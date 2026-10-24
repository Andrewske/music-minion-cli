/**
 * Default device names. Two devices of the same kind (two Android phones, two
 * Chrome tabs on different Macs) used to register with the same name, so the
 * device sheet listed "Android Phone" twice. The default now carries a short
 * suffix taken from the persisted device id, which keeps it stable across
 * restarts. Custom names (set via renameDevice) are used as-is.
 */

const SUFFIX_LENGTH = 4;
export const UNKNOWN_DEVICE_LABEL = 'Unknown device';

/** First few alphanumeric characters of the device id, lowercased. */
export function deviceIdSuffix(deviceId: string): string {
  return deviceId.replace(/[^a-z0-9]/gi, '').slice(0, SUFFIX_LENGTH).toLowerCase();
}

/** `<label> (<id suffix>)`, e.g. "Pixel 9 Pro (3f2a)". */
export function defaultDeviceName(label: string, deviceId: string): string {
  const base = label.trim() || UNKNOWN_DEVICE_LABEL;
  const suffix = deviceIdSuffix(deviceId);
  return suffix ? `${base} (${suffix})` : base;
}

/** The stored custom name when there is one, else the default name. */
export function resolveDeviceName(customName: string | null, label: string, deviceId: string): string {
  const custom = customName?.trim();
  return custom ? custom : defaultDeviceName(label, deviceId);
}
