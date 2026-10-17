import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Bot, History, Plus, X } from 'lucide-react'
import {
  CAPTURE_EXCLUDE_ATTR,
  collectPageContext,
  foldEvents,
  isBusy,
  liveAt,
  shippableId,
  usePageChat,
} from 'page-chat-core'
import { cn } from '../../lib/utils'
import { ChatItemView } from './ChatItems'
import { Composer } from './Composer'
import { HistoryList } from './HistoryList'
import { ReloadPill } from './ShipItems'
import { PAGE_CHAT_REPO, PAGE_CHAT_SECTION, shouldOfferReload, statusText } from './page-chat-view'

const HEADER_BUTTON = 'flex h-9 w-9 items-center justify-center rounded-full text-white/50 transition-colors hover:text-white'

interface HeaderButtonProps {
  label: string
  onClick: () => void
  active?: boolean
  children: ReactNode
}

function HeaderButton({ label, onClick, active = false, children }: HeaderButtonProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(HEADER_BUTTON, active && 'bg-obsidian-border text-white')}
    >
      {children}
    </button>
  )
}

interface HeaderProps {
  status: string | null
  canReset: boolean
  historyOpen: boolean
  onHistory: () => void
  onNew: () => void
}

function Header({ status, canReset, historyOpen, onHistory, onNew }: HeaderProps): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <Bot className="h-5 w-5 shrink-0 text-obsidian-accent" />
      <div className="min-w-0 flex-1">
        <Dialog.Title className="truncate font-inter text-[15px] font-semibold text-white">Music Minion agent</Dialog.Title>
        <p className={cn('text-xs text-white/40', status && 'animate-pulse')}>{status ?? 'Asks before it deploys anything.'}</p>
      </div>
      <HeaderButton label={historyOpen ? 'Back to the conversation' : 'Past conversations'} onClick={onHistory} active={historyOpen}>
        <History className="h-4 w-4" />
      </HeaderButton>
      {canReset && (
        <HeaderButton label="New conversation" onClick={onNew}>
          <Plus className="h-4 w-4" />
        </HeaderButton>
      )}
      <Dialog.Close aria-label="Close" title="Close" className={HEADER_BUTTON}>
        <X className="h-4 w-4" />
      </Dialog.Close>
    </div>
  )
}

function EmptyHint(): JSX.Element {
  return (
    <p className="m-auto max-w-xs text-center text-sm text-white/40">
      Ask about this page or ask for a change. The agent sees which page you're on; tap the camera to show it what you
      see. It commits on its own branch and asks before shipping.
    </p>
  )
}

/** Keeps the newest event in view as replies stream in. */
function useScrollToEnd(lastId: number | undefined): React.RefObject<HTMLDivElement | null> {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [lastId])
  return endRef
}

/** The chat itself. Mounted only while the sheet is open, so nothing polls when it's closed. */
function ChatPanel(): JSX.Element {
  const chat = usePageChat(PAGE_CHAT_SECTION, true, { explicitSection: true })
  const [historyOpen, setHistoryOpen] = useState(false)
  const items = useMemo(() => foldEvents(chat.events), [chat.events])
  const shipId = shippableId(chat.events, chat.status)
  const showReload = shouldOfferReload(liveAt(chat.events, PAGE_CHAT_REPO), performance.timeOrigin)
  const endRef = useScrollToEnd(chat.events[chat.events.length - 1]?.id)
  const openThread = (id: string): void => {
    chat.openThread(id)
    setHistoryOpen(false)
  }

  return (
    <>
      <Header
        status={statusText(chat.status, chat.desktop)}
        canReset={chat.threadId !== null}
        historyOpen={historyOpen}
        onHistory={() => setHistoryOpen((open) => !open)}
        onNew={() => {
          chat.startNew()
          setHistoryOpen(false)
        }}
      />
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1">
        {historyOpen ? (
          <HistoryList sectionId={PAGE_CHAT_SECTION} currentId={chat.threadId} onOpen={openThread} />
        ) : items.length === 0 ? (
          <EmptyHint />
        ) : (
          items.map((item) => <ChatItemView key={item.id} item={item} shippableId={shipId} onShip={chat.ship} />)
        )}
        {showReload && <ReloadPill />}
        <div ref={endRef} />
      </div>
      {chat.error && <p className="text-[13px] text-red-400">{chat.error}</p>}
      {!historyOpen && (
        <Composer
          busy={isBusy(chat.status)}
          sending={chat.sending}
          onStop={chat.stop}
          onSend={(message, shot) => chat.send(message, collectPageContext(), shot)}
        />
      )}
    </>
  )
}

/**
 * Phone: bottom sheet over the lower 3/4 so the page stays visible.
 * Desktop: right-side panel. Non-modal, so the page and PlayerBar stay usable,
 * and excluded from screenshots so the agent sees the page, not the chat.
 */
export function PageChatSheet(): JSX.Element {
  return (
    <Dialog.Portal>
      <Dialog.Content
        {...{ [CAPTURE_EXCLUDE_ATTR]: true }}
        aria-describedby={undefined}
        onInteractOutside={(e) => e.preventDefault()}
        className={cn(
          'fixed inset-x-0 bottom-0 z-50 flex h-[75dvh] flex-col gap-3 border-t border-obsidian-border bg-obsidian-black p-4 shadow-2xl',
          'pb-[calc(1rem+env(safe-area-inset-bottom))] font-inter focus:outline-none',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=open]:duration-300',
          'data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom',
          'md:inset-y-0 md:left-auto md:right-0 md:h-auto md:w-[420px] md:border-l md:border-t-0',
          'md:data-[state=open]:slide-in-from-bottom-0 md:data-[state=closed]:slide-out-to-bottom-0',
          'md:data-[state=open]:slide-in-from-right md:data-[state=closed]:slide-out-to-right'
        )}
      >
        <ChatPanel />
      </Dialog.Content>
    </Dialog.Portal>
  )
}
