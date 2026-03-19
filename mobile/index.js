/**
 * Entry point — registers RNTP playback service before anything else.
 * This MUST be a plain .js file at the project root.
 */
import TrackPlayer from 'react-native-track-player';
import 'expo-router/entry';

TrackPlayer.registerPlaybackService(() => require('./services/playback'));
