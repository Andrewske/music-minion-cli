import type { ReactElement } from 'react';
import type { UnfollowCandidate } from '../../api/unfollowSuggestions';
import { TierBadge } from '../artists/RankTierMenu';
import { AccountRow, Chip } from '../follow-suggestions/AccountRow';
import { asTier } from '../follow-suggestions/format';
import { Button } from '../ui/button';
import { candidateChips, candidateName } from './format';

export interface CandidateHandlers {
  /** Bulk run going: rows wait. */
  disabled: boolean;
  isBusy: (id: number) => boolean;
  onUnfollow: (id: number) => void;
  onKeep: (id: number) => void;
}

function Details({ candidate }: { candidate: UnfollowCandidate }): ReactElement {
  const tier = candidate.tier ? asTier(candidate.tier) : null;
  return (
    <>
      {tier && <TierBadge tier={tier} />}
      {candidateChips(candidate).map((chip) => <Chip key={chip}>{chip}</Chip>)}
    </>
  );
}

export function CandidateRow({ candidate, handlers }: { candidate: UnfollowCandidate; handlers: CandidateHandlers }): ReactElement {
  const id = candidate.discovery_artist_id;
  const off = handlers.disabled || handlers.isBusy(id);
  const account = {
    key: String(id),
    soundcloud_user_id: candidate.soundcloud_user_id,
    display_name: candidateName(candidate),
    permalink: candidate.slug,
    avatar_url: candidate.avatar_url,
    followers: candidate.followers,
  };
  const actions = (
    <>
      <Button size="sm" variant="ghost" className="text-white/60" title={candidate.tier ? 'Keep (never suggest again)' : 'Keep at tier C (never suggest again)'} disabled={off} onClick={() => handlers.onKeep(id)}>
        Keep
      </Button>
      <Button size="sm" variant="outline" disabled={off} onClick={() => handlers.onUnfollow(id)}>
        Unfollow
      </Button>
    </>
  );
  return <AccountRow account={account} details={<Details candidate={candidate} />} actions={actions} />;
}
