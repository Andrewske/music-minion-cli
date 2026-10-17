import { useCallback, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useRouterState } from '@tanstack/react-router'
import { MessageSquareText } from 'lucide-react'
import { CAPTURE_EXCLUDE_ATTR } from 'page-chat-core'
import { cn } from '../../lib/utils'
import { PageChatSheet } from './PageChatSheet'
import { OPEN_STORAGE_KEY, chatButtonOffset } from './page-chat-view'

function readOpen(): boolean {
  return typeof window !== 'undefined' && window.sessionStorage.getItem(OPEN_STORAGE_KEY) === '1'
}

/*
 * Floating button above the PlayerBar that opens a chat with the music-minion
 * page agent. Open state survives reloads within the tab, so the sheet comes
 * back after a deploy refresh. Only the button and sheet are excluded from
 * screenshots; the PlayerBar stays in.
 */
export function PageChatWidget(): JSX.Element {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const [open, setOpen] = useState(readOpen)

  const toggle = useCallback((next: boolean): void => {
    window.sessionStorage.setItem(OPEN_STORAGE_KEY, next ? '1' : '0')
    setOpen(next)
  }, [])

  return (
    <Dialog.Root open={open} onOpenChange={toggle} modal={false}>
      {!open && (
        <Dialog.Trigger
          {...{ [CAPTURE_EXCLUDE_ATTR]: true }}
          aria-label="Chat with the page agent"
          title="Chat with the page agent"
          className={cn(
            'fixed right-3 z-40 flex h-10 w-10 items-center justify-center rounded-full md:right-4',
            'border border-obsidian-border bg-obsidian-surface/80 text-white/60 backdrop-blur',
            'transition-colors hover:border-obsidian-accent hover:text-white',
            chatButtonOffset(pathname)
          )}
        >
          <MessageSquareText className="h-4 w-4" />
        </Dialog.Trigger>
      )}
      <PageChatSheet />
    </Dialog.Root>
  )
}
