import { Check, GitCommitHorizontal, Loader2, Rocket, RotateCw, X } from 'lucide-react'
import type { DeployMeta, DeployState, RepoChange } from 'page-chat-core'
import { Button } from '../ui/button'
import { cn } from '../../lib/utils'
import { deployLabel } from './page-chat-view'

function RepoBlock({ change }: { change: RepoChange }): JSX.Element {
  return (
    <div className="space-y-1">
      <p className="font-sf-mono text-xs font-semibold text-white/90">{change.repo}</p>
      <ul className="space-y-0.5">
        {change.commits.map((c) => (
          <li key={c.sha} className="flex gap-1.5 text-sm text-white/70">
            <GitCommitHorizontal className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/40" />
            <span>{c.subject}</span>
          </li>
        ))}
      </ul>
      <details className="text-xs text-white/40">
        <summary className="cursor-pointer">{change.shortstat || 'Changed files'}</summary>
        <ul className="mt-1 space-y-0.5 overflow-x-auto font-sf-mono">
          {change.files.map((f) => (
            <li key={f} className="whitespace-pre">{f}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}

interface ShipCardProps {
  repos: RepoChange[]
  /** Only the newest, still-current card can ship; older ones stay as a record. */
  shippable: boolean
  onShip: () => void
}

/** What the agent committed, plus the one button that pushes and deploys it. */
export function ShipCard({ repos, shippable, onShip }: ShipCardProps): JSX.Element {
  return (
    <div className={cn('space-y-3 border border-obsidian-border bg-obsidian-surface p-3', !shippable && 'opacity-60')}>
      {repos.map((change) => (
        <RepoBlock key={change.repo} change={change} />
      ))}
      {shippable ? (
        <Button size="sm" onClick={onShip} className="w-full gap-2">
          <Rocket className="h-4 w-4" /> Ship it
        </Button>
      ) : (
        <p className="text-xs text-white/40">Superseded by a newer change or already shipped.</p>
      )}
    </div>
  )
}

function StateIcon({ state }: { state: DeployState }): JSX.Element {
  if (state === 'live') return <Check className="h-3.5 w-3.5 text-obsidian-accent" />
  if (state === 'failed') return <X className="h-3.5 w-3.5 text-red-400" />
  return <Loader2 className="h-3.5 w-3.5 animate-spin text-white/40" />
}

function DeployRow({ step }: { step: DeployMeta }): JSX.Element {
  return (
    <li className="space-y-1">
      <p className="flex flex-wrap items-center gap-2 text-sm text-white/70">
        <StateIcon state={step.state} />
        <span className="font-sf-mono text-xs font-semibold text-white/90">{step.repo}</span>
        <span>{deployLabel(step)}</span>
        {step.sha && <span className="font-sf-mono text-xs text-white/40">{step.sha}</span>}
      </p>
      {step.detail && (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap bg-obsidian-black p-2 font-sf-mono text-[11px] text-white/60">
          {step.detail}
        </pre>
      )}
    </li>
  )
}

/** One row per repo being shipped; each updates in place as its deploy moves along. */
export function DeployRows({ steps }: { steps: DeployMeta[] }): JSX.Element {
  return (
    <ul className="space-y-2 border border-obsidian-border bg-obsidian-surface p-3">
      {steps.map((s) => (
        <DeployRow key={s.repo} step={s} />
      ))}
    </ul>
  )
}

/** Shown once the music-minion deploy is live: this tab still runs the old build until it reloads. */
export function ReloadPill(): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => window.location.reload()}
      className="mx-auto flex items-center gap-2 rounded-full bg-obsidian-accent px-4 py-2 text-sm font-semibold text-black hover:bg-obsidian-accent/90"
    >
      <RotateCw className="h-4 w-4" /> Deployed. Reload to see it
    </button>
  )
}
