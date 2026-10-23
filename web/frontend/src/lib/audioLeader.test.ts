import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Grant = () => Promise<never>;
interface Waiter {
  grant: Grant;
  reject: (err: Error) => void;
}

/** Minimal single-lock Web Locks fake: FIFO queue + steal. */
function createFakeLocks(): { request: LockManager['request'] } {
  let holder: Waiter | null = null;
  const queue: Waiter[] = [];

  const run = (w: Waiter): void => {
    holder = w;
    void w.grant();
  };

  const request = (
    _name: string,
    opts: LockOptions,
    grant: Grant,
  ): Promise<never> =>
    new Promise<never>((_resolve, reject) => {
      const w: Waiter = { grant, reject };
      if (opts.steal && holder) {
        holder.reject(new DOMException('stolen', 'AbortError'));
        run(w);
      } else if (holder) {
        queue.push(w);
      } else {
        run(w);
      }
    });

  return { request: request as unknown as LockManager['request'] };
}

/** Each "tab" is a fresh module instance sharing one fake lock manager. */
async function openTab(): Promise<{
  leader: () => boolean;
  claim: () => void;
}> {
  vi.resetModules();
  const mod = await import('./audioLeader');
  let isLeader = false;
  mod.startAudioLeaderElection((v) => {
    isLeader = v;
  });
  await Promise.resolve();
  return { leader: () => isLeader, claim: mod.claimAudioLeadership };
}

function setUserActivation(isActive: boolean): void {
  Object.defineProperty(navigator, 'userActivation', {
    value: { isActive, hasBeenActive: isActive },
    configurable: true,
  });
}

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

describe('audioLeader', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'locks', { value: createFakeLocks(), configurable: true });
  });

  afterEach(() => {
    Reflect.deleteProperty(navigator, 'locks');
    Reflect.deleteProperty(navigator, 'userActivation');
  });

  it('first tab leads, second waits', async () => {
    const a = await openTab();
    const b = await openTab();
    expect(a.leader()).toBe(true);
    expect(b.leader()).toBe(false);
  });

  it('a user tap steals leadership from a stuck background tab', async () => {
    const a = await openTab();
    const b = await openTab();
    setUserActivation(true);

    b.claim();
    await flush();

    expect(b.leader()).toBe(true);
    expect(a.leader()).toBe(false);
  });

  it('does not steal without a user gesture', async () => {
    const a = await openTab();
    const b = await openTab();
    setUserActivation(false);

    b.claim();
    await flush();

    expect(a.leader()).toBe(true);
    expect(b.leader()).toBe(false);
  });
});
