import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { ComparisonView } from '../../components/ComparisonView';

export const Route = createFileRoute('/comparison/$playlistId')({
  component: ComparisonPlaylistRoute,
});

function ComparisonPlaylistRoute(): JSX.Element {
  const { playlistId } = Route.useParams();
  const navigate = useNavigate();

  const numericId = parseInt(playlistId, 10);

  if (isNaN(numericId)) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <h1 className="text-white/60 text-sm">Invalid playlist ID</h1>
        <button
          type="button"
          onClick={() => navigate({ to: '/comparison' })}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Back
        </button>
      </div>
    );
  }

  // Pass the URL param down; ComparisonView starts/restores the session so direct
  // navigation and reloads load this playlist's comparison instead of the picker.
  return <ComparisonView playlistId={numericId} />;
}
