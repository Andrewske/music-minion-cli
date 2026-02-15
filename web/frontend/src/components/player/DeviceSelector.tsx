import { Speaker } from 'lucide-react';
import { usePlayer } from '../../hooks/usePlayer';
import { Button } from '../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';

export function DeviceSelector(): JSX.Element {
  const { availableDevices, activeDeviceId, thisDeviceId, setActiveDevice } = usePlayer();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="text-white/90 hover:text-white">
          <Speaker className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="bg-obsidian-surface border-obsidian-border">
        <DropdownMenuLabel className="text-white/60">Select Device</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {availableDevices.map((device) => (
          <DropdownMenuItem
            key={device.id}
            onClick={() => setActiveDevice(device.id)}
            className="text-white/90 hover:bg-white/10 cursor-pointer"
          >
            <div className="flex items-center gap-2">
              {device.id === activeDeviceId && (
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              )}
              <span>{device.name}</span>
              {device.id === thisDeviceId && (
                <span className="text-xs text-white/50">(this device)</span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
        {availableDevices.length === 0 && (
          <DropdownMenuItem disabled className="text-white/50">
            No devices available
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
