import { createRootRoute, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { useSyncWebSocket } from '../hooks/useSyncWebSocket'
import { PlayerBar } from '../components/player/PlayerBar'
import { Sidebar } from '../components/sidebar/Sidebar'
import { MobileHeader } from '../components/sidebar/MobileHeader'
import { SidebarPlaylists } from '../components/sidebar/SidebarPlaylists'
import { SidebarFilters } from '../components/sidebar/SidebarFilters'

function RootComponent(): JSX.Element {
  useSyncWebSocket() // Connect to sync WebSocket for real-time updates

  return (
    <div className="flex h-screen bg-black">
      {/* Mobile header - only on small screens */}
      <MobileHeader />

      {/* Desktop sidebar - only on md+ */}
      <div className="hidden md:flex">
        <Sidebar>
          <SidebarPlaylists sidebarExpanded={true} />
          <SidebarFilters sidebarExpanded={true} />
        </Sidebar>
      </div>

      {/* Main content area */}
      <main className="flex-1 min-w-0 overflow-y-auto pt-12 md:pt-0 pb-16">
        <Outlet />
      </main>

      {/* Player bar - fixed bottom */}
      <PlayerBar />

      {/* Dev tools */}
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  )
}

export const Route = createRootRoute({
  component: RootComponent,
})
