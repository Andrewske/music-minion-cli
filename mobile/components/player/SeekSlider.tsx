/**
 * Seek slider with timestamps.
 * Plain slider (no waveform — no good RN equivalent).
 */
import { View, Text, StyleSheet } from 'react-native';
import Slider from '@react-native-community/slider';

interface SeekSliderProps {
  position: number; // seconds
  duration: number; // seconds
  onSeek: (seconds: number) => void;
}

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

export function SeekSlider({ position, duration, onSeek }: SeekSliderProps) {
  return (
    <View style={styles.container}>
      <Slider
        style={styles.slider}
        value={position}
        minimumValue={0}
        maximumValue={duration || 1}
        minimumTrackTintColor="#7C4DFF"
        maximumTrackTintColor="#333"
        thumbTintColor="#7C4DFF"
        onSlidingComplete={onSeek}
      />
      <View style={styles.times}>
        <Text style={styles.time}>{formatTime(position)}</Text>
        <Text style={styles.time}>{formatTime(duration)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    paddingHorizontal: 4,
  },
  slider: {
    width: '100%',
    height: 40,
  },
  times: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
    marginTop: -8,
  },
  time: {
    color: '#9E9E9E',
    fontSize: 11,
    fontFamily: 'monospace',
  },
});
