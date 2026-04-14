import type { ReactElement } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { SlidersHorizontal } from 'lucide-react';
import { Button } from '../ui/button';
import { CHIP_KEYS, type ChipKey } from './ArtistStatChip';
import { useArtistViewStore } from '../../stores/artistViewStore';

const CHIP_LABELS: Record<ChipKey, string> = {
  library: 'Library count',
  reposts: 'Reposts in library',
  hit_rate: 'Hit rate',
  first_loved: 'First loved',
  feed_noise: 'Feed noise',
  activity: 'Activity',
  elo: 'Average ELO',
  followers: 'Followers',
};

export function ChipVisibilityMenu(): ReactElement {
  const { hiddenChips, toggleChip } = useArtistViewStore();

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5 font-sf-mono text-xs">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          Chips
        </Button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[180px] bg-obsidian-surface border border-obsidian-border py-1 shadow-lg"
        >
          {CHIP_KEYS.map((key) => {
            const isChecked = !hiddenChips.includes(key);
            return (
              <DropdownMenu.CheckboxItem
                key={key}
                checked={isChecked}
                onCheckedChange={() => toggleChip(key)}
                className="flex items-center gap-2 px-3 py-1.5 font-sf-mono text-xs text-white/70 hover:text-white hover:bg-white/5 cursor-pointer focus:outline-none focus:bg-white/5"
              >
                <DropdownMenu.ItemIndicator>
                  <span className="w-3 h-3 inline-flex items-center justify-center text-obsidian-accent">✓</span>
                </DropdownMenu.ItemIndicator>
                {!isChecked && <span className="w-3 h-3" />}
                {CHIP_LABELS[key]}
              </DropdownMenu.CheckboxItem>
            );
          })}

          <DropdownMenu.Separator className="my-1 border-t border-obsidian-border" />
          <DropdownMenu.Item
            onSelect={() => useArtistViewStore.getState().showAll()}
            className="px-3 py-1.5 font-sf-mono text-xs text-white/40 hover:text-white hover:bg-white/5 cursor-pointer focus:outline-none focus:bg-white/5"
          >
            Show all
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
