/**
 * Organizer session header: ← back to picker, playlist name, session name +
 * progress, and a Sessions button that opens the session switcher sheet.
 */
import { Layers } from 'lucide-react-native';
import type { BucketSession } from '@music-minion/shared';
import { HeaderIconButton, ScreenHeader } from '../ScreenHeader';
import type { SessionCounts } from '../../features/organizer/organizerState';
import { sessionSubtitle } from '../../features/organizer/sessionSwitcher';

interface SessionHeaderProps {
  playlistName: string;
  session: BucketSession | undefined;
  counts: SessionCounts;
  onBack: () => void;
  /** Omit to hide the Sessions button (e.g. while loading). */
  onOpenSessions?: () => void;
  sessionsDisabled?: boolean;
}

export function SessionHeader(props: SessionHeaderProps): React.JSX.Element {
  const { playlistName, session, counts, onBack, onOpenSessions, sessionsDisabled } = props;
  const sessionsButton = onOpenSessions ? (
    <HeaderIconButton icon={Layers} label="Sessions" testID="organizer-sessions-btn" onPress={onOpenSessions} disabled={sessionsDisabled} />
  ) : undefined;
  return (
    <ScreenHeader
      title={playlistName}
      titleTestID="organizer-session-title"
      subtitle={sessionSubtitle(session, counts)}
      subtitleTestID="organizer-session-counts"
      onBack={onBack}
      backLabel="Back to playlists"
      backTestID="organizer-back-btn"
      right={sessionsButton}
    />
  );
}
