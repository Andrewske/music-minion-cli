/**
 * Comparison session header: ← exit, playlist name, session progress, streak.
 */
import { View } from 'react-native';
import { StreakCounter } from './StreakCounter';
import { ScreenHeader } from '../ScreenHeader';
import { formatSessionProgress } from '../../features/comparison/comparisonState';

interface SessionHeaderProps {
  playlistName: string;
  voteCount: number;
  onExit: () => void;
}

export function SessionHeader({ playlistName, voteCount, onExit }: SessionHeaderProps): React.JSX.Element {
  return (
    <ScreenHeader
      title={playlistName}
      titleTestID="comparison-playlist-name"
      subtitle={formatSessionProgress(voteCount)}
      subtitleTestID="comparison-session-progress"
      onBack={onExit}
      backLabel="Exit comparison session"
      backTestID="comparison-exit"
      right={
        <View style={{ paddingRight: 8 }}>
          <StreakCounter voteCount={voteCount} />
        </View>
      }
    />
  );
}
