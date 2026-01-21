# Create TanStack Router File Structure

## Files to Modify/Create
- `web/frontend/src/routes/__root.tsx` (new)
- `web/frontend/src/routes/index.tsx` (new)
- `web/frontend/src/routes/playlist-builder/index.tsx` (new)
- `web/frontend/src/routes/playlist-builder/$playlistName.tsx` (new)

## Implementation Details

Create the route directory structure and base route files:

```bash
mkdir -p web/frontend/src/routes/playlist-builder
```

### File 1: Root Route (`__root.tsx`)

```typescript
import { createRootRoute, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen">
      <Outlet />
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  ),
})
```

### File 2: Index Route (`index.tsx`)

```typescript
import { createFileRoute } from '@tanstack/react-router'
import { ComparisonView } from '../components/ComparisonView'

export const Route = createFileRoute('/')({
  component: ComparisonView,
})
```

### Purpose
- **__root.tsx**: Root layout with `<Outlet />` for child routes and DevTools
- **index.tsx**: Maps root path `/` to existing ComparisonView component

## Acceptance Criteria
- [ ] Directory `web/frontend/src/routes/` created
- [ ] Directory `web/frontend/src/routes/playlist-builder/` created
- [ ] `__root.tsx` created with Outlet and DevTools
- [ ] `index.tsx` created mapping to ComparisonView
- [ ] All imports resolve correctly

## Dependencies
- Task 02 (Vite plugin must be configured)
- ComparisonView component must exist at `../components/ComparisonView`
