import { createFileRoute } from '@tanstack/react-router';
import { ComparisonView } from '../../components/ComparisonView';

export const Route = createFileRoute('/comparison/')({
  component: ComparisonIndexRoute,
});

function ComparisonIndexRoute(): JSX.Element {
  // No playlist in the URL: ComparisonView renders the playlist picker.
  // Selecting a playlist navigates to /comparison/$playlistId.
  return <ComparisonView />;
}
