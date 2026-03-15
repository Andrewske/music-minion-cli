import { useState, useRef, useEffect } from 'react';
import { Speaker, Pencil, Check, X } from 'lucide-react';
import { usePlayerStore } from '../../stores/playerStore';
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
  const availableDevices = usePlayerStore((s) => s.availableDevices);
  const activeDeviceId = usePlayerStore((s) => s.activeDeviceId);
  const thisDeviceId = usePlayerStore((s) => s.thisDeviceId);
  const thisDeviceName = usePlayerStore((s) => s.thisDeviceName);
  const setActiveDevice = usePlayerStore((s) => s.setActiveDevice);
  const renameDevice = usePlayerStore((s) => s.renameDevice);

  const [isRenaming, setIsRenaming] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isRenaming]);

  const startRename = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setNameInput(thisDeviceName);
    setIsRenaming(true);
  };

  const confirmRename = () => {
    renameDevice(nameInput);
    setIsRenaming(false);
  };

  const cancelRename = () => {
    setIsRenaming(false);
  };

  return (
    <DropdownMenu onOpenChange={(open) => { if (!open) setIsRenaming(false); }}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="text-white/90 hover:text-white">
          <Speaker className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="bg-obsidian-surface border-obsidian-border">
        <DropdownMenuLabel className="text-white/60">Select Device</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {availableDevices.map((device) => {
          const isThisDevice = device.id === thisDeviceId;
          const isActive = device.id === activeDeviceId;

          // Inline rename for this device
          if (isThisDevice && isRenaming) {
            return (
              <div key={device.id} className="flex items-center gap-1 px-2 py-1.5">
                {isActive && (
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
                )}
                <input
                  ref={inputRef}
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') confirmRename();
                    if (e.key === 'Escape') cancelRename();
                    e.stopPropagation();
                  }}
                  className="flex-1 bg-black/50 border border-obsidian-border rounded px-2 py-0.5 text-sm text-white outline-none focus:border-obsidian-accent min-w-0"
                />
                <button onClick={confirmRename} className="p-1 text-green-400 hover:text-green-300">
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button onClick={cancelRename} className="p-1 text-white/40 hover:text-white/60">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          }

          return (
            <DropdownMenuItem
              key={device.id}
              onClick={() => setActiveDevice(device.id)}
              className="text-white/90 hover:bg-white/10 cursor-pointer"
            >
              <div className="flex items-center gap-2 w-full">
                {isActive && (
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                )}
                <span>{device.name}</span>
                {isThisDevice && (
                  <>
                    <span className="text-xs text-white/50">(this device)</span>
                    <button
                      onClick={startRename}
                      className="ml-auto p-1 text-white/30 hover:text-white/60"
                    >
                      <Pencil className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            </DropdownMenuItem>
          );
        })}
        {availableDevices.length === 0 && (
          <DropdownMenuItem disabled className="text-white/50">
            No devices available
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
