import 'react-native-get-random-values';

if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout !== 'function') {
  AbortSignal.timeout = (ms) => {
    const controller = new AbortController();
    const err = new Error('The operation timed out.');
    err.name = 'TimeoutError';
    setTimeout(() => controller.abort(err), ms);
    return controller.signal;
  };
}

if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
  crypto.randomUUID = () => {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0'));
    return [
      hex.slice(0, 4).join(''),
      hex.slice(4, 6).join(''),
      hex.slice(6, 8).join(''),
      hex.slice(8, 10).join(''),
      hex.slice(10).join(''),
    ].join('-');
  };
}

import TrackPlayer from '@rntp/player';
import 'expo-router/entry';

TrackPlayer.registerBackgroundEventHandler(() => require('./services/playback'));
