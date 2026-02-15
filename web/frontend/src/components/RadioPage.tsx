import { RadioPlayer } from './RadioPlayer';
import { UpNext } from './UpNext';
import { StationsList } from './StationsList';

export function RadioPage(): JSX.Element {
  return (
    <div className="min-h-screen bg-black text-white p-6">
      <h1 className="text-2xl font-bold mb-6">Personal Radio</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Now Playing + Up Next */}
        <div className="lg:col-span-2 space-y-6">
          <RadioPlayer />
          <UpNext />
        </div>

        {/* Right: Stations */}
        <div>
          <StationsList />
        </div>
      </div>
    </div>
  );
}
