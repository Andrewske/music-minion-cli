/**
 * Entry point — registers RNTP playback service before anything else.
 * This MUST be a plain .js file at the project root.
 */
import 'react-native-get-random-values'; // Polyfill crypto.getRandomValues for Hermes

// Polyfill crypto.randomUUID (uses getRandomValues which is now available)
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

import TrackPlayer from 'react-native-track-player';
import 'expo-router/entry';

TrackPlayer.registerPlaybackService(() => require('./services/playback'));
