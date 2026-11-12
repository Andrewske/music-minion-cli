import type { ReactElement, ReactNode } from 'react';
import { ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';
import { formatFollowers, soundcloudSearchUrl, soundcloudUrl } from './format';

export interface RowAccount {
  key: string;
  soundcloud_user_id: string | null;
  display_name: string;
  permalink: string | null;
  avatar_url: string | null;
  followers: number | null;
}

export function Avatar({ url, name, size = 40 }: { url: string | null; name: string; size?: number }): ReactElement {
  const box = { width: size, height: size };
  if (url) return <img src={url} alt="" style={box} className="object-cover shrink-0" loading="lazy" />;
  return (
    <div style={box} className="shrink-0 flex items-center justify-center bg-obsidian-border text-white/70 font-inter text-sm select-none">
      {name.charAt(0).toUpperCase()}
    </div>
  );
}

function AccountName({ account }: { account: RowAccount }): ReactElement {
  const cls = 'font-inter text-sm font-medium text-white truncate';
  if (!account.permalink) return <span className={cls}>{account.display_name}</span>;
  return (
    <a href={soundcloudUrl(account.permalink)} target="_blank" rel="noreferrer" className={`${cls} hover:underline`}>
      {account.display_name}
    </a>
  );
}

interface FollowActionsProps {
  account: RowAccount;
  followDisabled: boolean;
  onFollow: (soundcloudUserId: string) => void;
  onDismiss: (key: string) => void;
}

/** Follow (or a SoundCloud search link for unresolved names) plus a permanent Dismiss. */
export function FollowActions({ account, followDisabled, onFollow, onDismiss }: FollowActionsProps): ReactElement {
  const id = account.soundcloud_user_id;
  return (
    <>
      {id != null ? (
        <Button size="sm" variant="outline" disabled={followDisabled} onClick={() => onFollow(id)}>
          Follow
        </Button>
      ) : (
        <a
          href={soundcloudSearchUrl(account.display_name)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 h-8 px-3 text-xs text-white/70 border border-obsidian-border hover:text-white"
        >
          Search on SoundCloud <ExternalLink className="w-3 h-3" />
        </a>
      )}
      <Button size="sm" variant="ghost" className="text-white/50" onClick={() => onDismiss(account.key)}>
        Dismiss
      </Button>
    </>
  );
}

interface AccountRowProps {
  account: RowAccount;
  /** Chips or other details under the name. */
  details: ReactNode;
  actions: ReactNode;
  /** Optional expanded content below the row. */
  children?: ReactNode;
  quiet?: boolean;
}

export function AccountRow({ account, details, actions, children, quiet = false }: AccountRowProps): ReactElement {
  return (
    <li data-testid={`account-row-${account.key}`} className={`border-b border-obsidian-border py-3 ${quiet ? 'opacity-70' : ''}`}>
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <Avatar url={account.avatar_url} name={account.display_name} size={quiet ? 32 : 40} />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2 min-w-0">
              <AccountName account={account} />
              {account.followers != null && (
                <span className="font-sf-mono text-[10px] text-white/40 shrink-0">{formatFollowers(account.followers)} followers</span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">{details}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">{actions}</div>
      </div>
      {children}
    </li>
  );
}

export function Chip({ children }: { children: ReactNode }): ReactElement {
  return <span className="font-sf-mono text-[11px] text-white/60 border border-obsidian-border px-1.5 py-px">{children}</span>;
}
