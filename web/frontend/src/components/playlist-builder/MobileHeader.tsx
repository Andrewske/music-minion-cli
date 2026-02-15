import { useState } from "react";
import { Sheet, SheetContent } from "../ui/sheet";
import type { Filter } from "../../api/builder";
import { FilterSidebar } from "./FilterSidebar";

interface MobileHeaderProps {
  playlistName: string;
  onBack: () => void;
  filters: Filter[];
  onUpdateFilters: (filters: Filter[]) => void;
  isUpdatingFilters: boolean;
  playlistId: number;
}

export function MobileHeader({
  playlistName,
  onBack,
  filters,
  onUpdateFilters,
  isUpdatingFilters,
  playlistId,
}: MobileHeaderProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Fixed header - mobile only */}
      <div className="fixed left-0 right-0 top-0 z-50 flex h-10 items-center border-b border-obsidian-border bg-black px-3 md:hidden">
        {/* Hamburger button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`flex h-8 w-8 items-center justify-center rounded transition-colors ${
            isOpen ? "bg-obsidian-accent text-black" : "text-white/60 hover:text-white"
          }`}
          aria-label={isOpen ? "Close menu" : "Open menu"}
        >
          {isOpen ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          )}
        </button>

        {/* Playlist name */}
        <div className="flex flex-1 items-center justify-center">
          <span className="text-sm font-sf-mono text-white/60 truncate max-w-[200px]">
            {playlistName}
          </span>
        </div>

        {/* Back button */}
        <button
          onClick={onBack}
          className="text-white/40 hover:text-obsidian-accent transition-colors text-sm"
        >
          Back
        </button>
      </div>

      {/* Filter sheet - positioned below header */}
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent side="left" belowHeader>
          <div className="p-4 h-full overflow-y-auto">
            <FilterSidebar
              filters={filters}
              onUpdate={(f) => {
                onUpdateFilters(f);
              }}
              isUpdating={isUpdatingFilters}
              playlistId={playlistId}
            />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
