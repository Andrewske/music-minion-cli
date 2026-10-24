/**
 * Device labels for the player bar and device sheet. Pure: callers pass the
 * slices of the shared player store (`availableDevices`, `activeDeviceId`,
 * `thisDeviceId`) they need.
 */
import type { Device } from '@music-minion/shared';

export const FALLBACK_DEVICE_NAME = 'another device';

export interface DeviceRow {
  id: string;
  name: string;
  isActive: boolean;
}

/** Name of the device that owns playback, or "another device" if unknown. */
export function activeDeviceName(devices: readonly Device[], activeDeviceId: string | null): string {
  const match = devices.find((d) => d.id === activeDeviceId);
  const name = match?.name.trim();
  return name ? name : FALLBACK_DEVICE_NAME;
}

export interface SecondLineInput {
  isThisDeviceActive: boolean;
  artist: string | undefined;
  devices: readonly Device[];
  activeDeviceId: string | null;
}

export interface SecondLine {
  text: string;
  /** True when the line names a remote device (accent color, opens the sheet). */
  isRemote: boolean;
}

/** Mini bar second line: the artist here, `on <device>` when elsewhere. */
export function playerSecondLine(input: SecondLineInput): SecondLine {
  if (input.isThisDeviceActive) {
    return { text: input.artist ?? 'Unknown Artist', isRemote: false };
  }
  return { text: `on ${activeDeviceName(input.devices, input.activeDeviceId)}`, isRemote: true };
}

/**
 * Devices other than this one, for the sheet's list. The active device comes
 * first; the rest keep the server's order.
 */
export function otherDeviceRows(
  devices: readonly Device[],
  thisDeviceId: string,
  activeDeviceId: string | null,
): DeviceRow[] {
  const rows = devices
    .filter((d) => d.id !== thisDeviceId)
    .map((d) => ({ id: d.id, name: d.name.trim() || 'Unnamed device', isActive: d.id === activeDeviceId }));
  return [...rows.filter((r) => r.isActive), ...rows.filter((r) => !r.isActive)];
}
