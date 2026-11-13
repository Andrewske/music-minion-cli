import type { ReactElement } from 'react';
import type { FollowConnection } from '../../api/followSuggestions';
import { useFollowConnections } from '../../hooks/useFollowSuggestions';
import { TierBadge } from '../artists/RankTierMenu';
import { AccountRow, FollowActions } from './AccountRow';
import { asTier } from './format';
import type { SuggestionHandlers } from './SuggestionRow';

function ViaChips({ connection }: { connection: FollowConnection }): ReactElement {
  return (
    <>
      {connection.via.map((v) => {
        const tier = asTier(v.tier);
        return (
          <span key={`${v.discovery_artist_id}-${v.relation}`} title={v.relation} className="inline-flex items-center gap-1 font-sf-mono text-[11px] text-white/60 border border-obsidian-border px-1.5 py-px">
            {v.display_name}
            {tier && <TierBadge tier={tier} />}
          </span>
        );
      })}
    </>
  );
}

function ConnectionList({ title, rows, handlers }: { title: string; rows: FollowConnection[]; handlers: SuggestionHandlers }): ReactElement | null {
  if (rows.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="font-sf-mono text-xs uppercase tracking-wide text-white/40">{title}</h3>
      <ul>
        {rows.map((c) => (
          <AccountRow
            key={c.key}
            account={c}
            details={<ViaChips connection={c} />}
            actions={<FollowActions account={c} followDisabled={handlers.followDisabled} busy={handlers.isBusy(c)} onFollow={handlers.onFollow} onDismiss={handlers.onDismiss} />}
          />
        ))}
      </ul>
    </div>
  );
}

/** Hidden quietly while loading, on error, or when both lists are empty. */
export function ConnectionsSection({ handlers }: { handlers: SuggestionHandlers }): ReactElement | null {
  const { data, error } = useFollowConnections();
  if (error || !data || (data.co_credit.length === 0 && data.favorites_follow.length === 0)) return null;
  return (
    <section aria-labelledby="fs-connections" className="mt-10">
      <h2 id="fs-connections" className="font-inter text-lg font-semibold text-white">Your favorites' connections</h2>
      <ConnectionList title="Works with your top artists" rows={data.co_credit} handlers={handlers} />
      <ConnectionList title="Your favorites follow" rows={data.favorites_follow} handlers={handlers} />
    </section>
  );
}
