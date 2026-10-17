import { useEffect } from 'react'
import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { PageChatProvider, listenForPageErrors } from 'page-chat-core'
import { useSyncWebSocket } from '../hooks/useSyncWebSocket'
import { PlayerBar } from '../components/player/PlayerBar'
import { Sidebar } from '../components/sidebar/Sidebar'
import { MobileHeader } from '../components/sidebar/MobileHeader'
import { SidebarPlaylists } from '../components/sidebar/SidebarPlaylists'
import { SidebarFilters } from '../components/sidebar/SidebarFilters'
import { SidebarQuickTag } from '../components/sidebar/SidebarQuickTag'
import { AudioElementProvider } from '../contexts/AudioElementContext'
import { PageChatWidget } from '../components/page-chat/PageChatWidget'

function RootComponent(): JSX.Element {
  useSyncWebSocket() // Connect to sync WebSocket for real-time updates
  useEffect(listenForPageErrors, []) // Idempotent; buffers errors so page-chat messages carry them

  // Comparison route has expanded PlayerBar (h-32) and handles its own spacing
  const routerState = useRouterState()
  const isComparisonRoute = routerState.location.pathname === '/comparison'
  const bottomPadding = isComparisonRoute ? 'pb-0' : 'pb-16'

  return (
    <AudioElementProvider>
      <PageChatProvider>
        <div className="flex h-screen supports-[height:100dvh]:h-dvh bg-black">
          {/* Mobile header - only on small screens */}
          <MobileHeader>
            <SidebarQuickTag sidebarExpanded={true} />
            <SidebarPlaylists sidebarExpanded={true} />
            <SidebarFilters sidebarExpanded={true} />
          </MobileHeader>

          {/* Desktop sidebar - only on md+ */}
          <div className="hidden md:flex">
            <Sidebar>
              <SidebarQuickTag sidebarExpanded={true} />
              <SidebarPlaylists sidebarExpanded={true} />
              <SidebarFilters sidebarExpanded={true} />
            </Sidebar>
          </div>

          {/* Main content area */}
          <main className={`flex-1 min-w-0 overflow-y-auto pt-[calc(3rem+var(--safe-top,0px))] md:pt-0 ${bottomPadding}`}>
            <Outlet />
          </main>

          {/* Player bar - fixed bottom */}
          <PlayerBar />

          {/* Toast notifications */}
          <ToastContainer
            position="top-right"
            autoClose={3000}
            hideProgressBar={false}
            newestOnTop={false}
            closeOnClick
            rtl={false}
            pauseOnFocusLoss
            draggable
            pauseOnHover
            theme="dark"
          />

          {/* Page agent chat - floats above the PlayerBar */}
          <PageChatWidget />

          {/* Dev tools */}
          {import.meta.env.DEV && <TanStackRouterDevtools />}
        </div>
      </PageChatProvider>
    </AudioElementProvider>
  )
}

export const Route = createRootRoute({
  component: RootComponent,
})
