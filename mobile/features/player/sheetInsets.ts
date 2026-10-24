/**
 * Safe-area padding for the full player Modal.
 *
 * Android: the Modal is drawn edge-to-edge (statusBarTranslucent +
 * navigationBarTranslucent, and forced on anyway when RN's edge-to-edge flag
 * is set), and the root layout's SafeAreaView padding does not reach inside a
 * Modal's window. So the sheet pads itself by the system bar insets.
 * iOS: pageSheet already starts below the status bar; only the home
 * indicator needs room.
 */

export interface Insets {
  top: number;
  bottom: number;
}

export function fullPlayerInsets(os: string, insets: Insets): Insets {
  if (os === 'android') return { top: insets.top, bottom: insets.bottom };
  return { top: 0, bottom: insets.bottom };
}
