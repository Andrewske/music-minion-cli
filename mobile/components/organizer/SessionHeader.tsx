/**
 * Organizer session header: ← back to picker, playlist name, progress counts.
 */
import { ScreenHeader } from '../ScreenHeader';
import type { SessionCounts } from '../../features/organizer/organizerState';

interface SessionHeaderProps {
  playlistName: string;
  counts: SessionCounts;
  onBack: () => void;
}

export function SessionHeader({ playlistName, counts, onBack }: SessionHeaderProps): React.JSX.Element {
  return (
    <ScreenHeader
      title={playlistName}
      titleTestID="organizer-session-title"
      subtitle={`${counts.assigned}/${counts.total} sorted · ${counts.unassigned} left · ${counts.buckets} buckets`}
      subtitleTestID="organizer-session-counts"
      onBack={onBack}
      backLabel="Back to playlists"
      backTestID="organizer-back-btn"
    />
  );
}
