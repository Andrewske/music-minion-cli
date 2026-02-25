---
task: 03-make-unassigned-tracks-draggable
status: pending
depends: [02-add-dnd-context-to-playlist-organizer]
files:
  - path: web/frontend/src/components/organizer/UnassignedTrackTable.tsx
    action: modify
---

# Make Unassigned Tracks Draggable

## Context
Add drag handles to the unassigned track table rows, making them draggable sources. Users can grab the handle icon and drag tracks to bucket drop zones. This integrates with the existing virtualized table (@tanstack/react-virtual) and preserves click-to-play functionality.

## Files to Modify
- `web/frontend/src/components/organizer/UnassignedTrackTable.tsx` (modify)

## Implementation Details

### 1. Add Imports
Add these imports at the top:
```typescript
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import type { Row } from '@tanstack/react-table';
```

### 2. Add Drag Handle Column
Insert after line 26 in the columns definition array:
```typescript
{
  id: 'drag',
  header: '',
  cell: () => null, // Rendered separately in DraggableRow
  size: 40,
  meta: { fixed: true },
},
```

### 3. Create DraggableRow Component
Add this component after line 113 (after the `getRowClasses` helper):

```typescript
interface DraggableRowProps {
  track: PlaylistTrackEntry;
  virtualRow: { start: number; size: number };
  row: Row<PlaylistTrackEntry>;
  isPlaying: boolean;
  onTrackClick: (trackId: number) => void;
  getColumnFlex: (column: Column<PlaylistTrackEntry>) => React.CSSProperties;
}

function DraggableRow({ track, virtualRow, row, isPlaying, onTrackClick, getColumnFlex }: DraggableRowProps): JSX.Element {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: track.id,
    data: { type: 'unassigned-track' },
  });

  const dragTransform = transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : '';
  const virtualTransform = `translateY(${virtualRow.start}px)`;
  const combinedTransform = transform ? dragTransform : virtualTransform;

  const rowClasses = `cursor-pointer hover:bg-white/5 transition-colors ${
    isPlaying ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent' : ''
  }`;

  return (
    <tr
      ref={setNodeRef}
      className={rowClasses}
      onClick={() => onTrackClick(track.id)}
      style={{
        display: 'flex',
        position: 'absolute',
        transform: combinedTransform,
        width: '100%',
        height: `${virtualRow.size}px`,
        opacity: isDragging ? 0.5 : 1,
      }}
    >
      {/* Drag handle */}
      <td
        className="px-3 py-2 border-b border-obsidian-border/50"
        style={{ flex: '0 0 40px', minWidth: 0 }}
      >
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 focus:outline-none focus:ring-2 focus:ring-obsidian-accent"
          onClick={(e) => e.stopPropagation()} // Prevent row click when grabbing
          tabIndex={0}
          role="button"
          aria-label={`Drag ${track.title} to assign to bucket`}
        >
          <GripVertical className="w-4 h-4" />
        </div>
      </td>

      {/* Existing cells (filter out drag column by ID, not position) */}
      {row.getVisibleCells()
        .filter(cell => cell.column.id !== 'drag')
        .map((cell) => (
        <td
          key={cell.id}
          className="px-3 py-2 border-b border-obsidian-border/50 overflow-hidden text-white/50"
          style={getColumnFlex(cell.column)}
        >
          <div className="truncate" title={String(cell.getValue() ?? '')}>
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </div>
        </td>
      ))}
    </tr>
  );
}
```

### 4. Replace Virtualizer Mapping
Replace the virtualizer mapping (lines 163-196) with:

```typescript
{virtualizer.getVirtualItems().map((virtualRow) => {
  const row = table.getRowModel().rows[virtualRow.index];
  const track = tracks[virtualRow.index];

  return (
    <DraggableRow
      key={row.id}
      track={track}
      virtualRow={virtualRow}
      row={row}
      isPlaying={track.id === currentTrackId}
      onTrackClick={onTrackClick}
      getColumnFlex={getColumnFlex}
    />
  );
})}
```

### Key Design Decisions
- **Transform combination**: Virtual scrolling transform takes precedence when not dragging; drag transform replaces it during drag
- **Click isolation**: Drag handle prevents row click via `stopPropagation()`, preserving click-to-play on the rest of the row
- **Visual feedback**: 50% opacity during drag, cursor changes (grab → grabbing), focus ring for keyboard navigation
- **Type tagging**: `data: { type: 'unassigned-track' }` allows DndContext to route correctly
- **Keyboard accessibility**: Drag handle is focusable (tabIndex={0}), has semantic role (button), and descriptive ARIA label. @dnd-kit's KeyboardSensor handles Arrow/Space keys automatically.
- **Column filtering**: Filters cells by `column.id !== 'drag'` instead of `slice(1)` for position-independent robustness

### Mobile Considerations
The drag handle works with touch devices via @dnd-kit's built-in touch support. The 8px activation constraint (from PointerSensor) prevents accidental drags during scrolling.

## Verification

### Mouse Interaction
1. In playlist organizer with unassigned tracks
2. Hover over the **leftmost column** with GripVertical icon
3. Cursor should change to grab hand
4. Click and drag → Track row should:
   - Have 50% opacity during drag
   - Follow the mouse cursor
   - Ghost image appears
5. Click on the rest of the row (not the handle) → Should still trigger click-to-play
6. Scroll the unassigned table → Virtual scrolling performance unchanged

### Keyboard Accessibility
1. Press Tab to focus on a drag handle → Should show focus ring (obsidian-accent)
2. Press Space while focused → Should initiate drag mode
3. Use Arrow keys to move the dragged item
4. Press Space again → Should drop the item
5. Screen reader should announce "Drag [Track Title] to assign to bucket"

### Mobile/Touch
1. Test on mobile/touch device → Drag should work with touch gestures

**Edge Cases**:
- Empty unassigned table → "All tracks assigned" message appears (no drag handles)
- Single unassigned track → Drag handle appears, drag works correctly
