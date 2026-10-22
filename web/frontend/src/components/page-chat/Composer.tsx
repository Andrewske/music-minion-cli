import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ArrowUp, Camera, Loader2, Square, X } from 'lucide-react'
import { MAX_MESSAGE_CHARS, captureVisible } from 'page-chat-core'

function ShotPreview({ shot, onRemove }: { shot: Blob; onRemove: () => void }): JSX.Element {
  const url = useMemo(() => URL.createObjectURL(shot), [shot])
  useEffect(() => (): void => URL.revokeObjectURL(url), [url])
  return (
    <div className="relative mx-2 mt-2 inline-block overflow-hidden border border-obsidian-border">
      <img src={url} alt="Screenshot to send with the message" className="max-h-24 w-auto" />
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove screenshot"
        className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 text-white/70 hover:text-white"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}

interface Screenshot {
  shot: Blob | null
  capturing: boolean
  take: () => Promise<void>
  clear: () => void
}

function useScreenshot(): Screenshot {
  const [shot, setShot] = useState<Blob | null>(null)
  const [capturing, setCapturing] = useState(false)
  const take = async (): Promise<void> => {
    setCapturing(true)
    setShot(await captureVisible('image/png'))
    setCapturing(false)
  }
  return { shot, capturing, take, clear: () => setShot(null) }
}

interface IconButtonProps {
  label: string
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}

function IconButton({ label, onClick, disabled, children }: IconButtonProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="flex h-11 w-9 shrink-0 items-center justify-center text-white/40 transition-colors hover:text-white disabled:opacity-40"
    >
      {children}
    </button>
  )
}

interface ComposerProps {
  busy: boolean
  sending: boolean
  onSend: (message: string, screenshot: Blob | null) => Promise<boolean>
  onStop: () => void
}

/** Message box with an opt-in screenshot of the page (the sheet itself is excluded from the capture). */
export function Composer({ busy, sending, onSend, onStop }: ComposerProps): JSX.Element {
  const [draft, setDraft] = useState('')
  const { shot, capturing, take, clear } = useScreenshot()
  const canSend = draft.trim() !== '' && !sending && !busy

  const send = async (): Promise<void> => {
    if (!canSend) return
    if (await onSend(draft.trim(), shot)) {
      setDraft('')
      clear()
    }
  }

  return (
    <div className="border border-obsidian-border bg-obsidian-surface">
      {shot && <ShotPreview shot={shot} onRemove={clear} />}
      <div className="flex items-end gap-1 p-2">
        <IconButton label={shot ? 'Retake screenshot' : 'Attach a screenshot of this page'} onClick={() => void take()} disabled={capturing}>
          {capturing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
        </IconButton>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== 'Enter' || e.shiftKey) return
            e.preventDefault()
            void send()
          }}
          rows={1}
          maxLength={MAX_MESSAGE_CHARS}
          placeholder="Ask, or request a change…"
          aria-label="Message"
          className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] text-white placeholder:text-white/30 focus:outline-hidden"
        />
        <button
          type="button"
          onClick={busy ? onStop : () => void send()}
          aria-label={busy ? 'Stop the agent' : 'Send'}
          title={busy ? 'Stop the agent' : 'Send'}
          disabled={!busy && !canSend}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-obsidian-accent text-black transition-opacity disabled:opacity-40"
        >
          {busy ? <Square className="h-4 w-4" /> : <ArrowUp className="h-5 w-5" />}
        </button>
      </div>
    </div>
  )
}
