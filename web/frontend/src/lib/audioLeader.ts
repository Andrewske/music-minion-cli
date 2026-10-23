/**
 * Cross-tab audio leader election via the Web Locks API.
 *
 * Every same-origin tab shares one persisted device-id, so the backend sees
 * them as a single device — but each tab owns its own <audio> elements. Only
 * the tab holding this lock may drive audio; the rest act as remote controls
 * (the same code path used when another device is active). The browser
 * releases the lock automatically when the holding tab closes or crashes,
 * promoting the longest-waiting tab — no heartbeats, no cleanup handlers.
 *
 * A tab the user is actually tapping play in can steal the lock
 * (claimAudioLeadership): otherwise a frozen background tab — common on
 * Android, where tabs are suspended but not closed — holds it forever and
 * the visible tab stays silent.
 */
const LOCK_NAME = 'music-minion-audio-leader';

let isLeader = false;
let notifyLeader: (isLeader: boolean) => void = () => {};

function setLeader(value: boolean): void {
  isLeader = value;
  notifyLeader(value);
}

/** Request the lock; on losing it to a steal, step down and queue again. */
function holdLock(steal: boolean): void {
  navigator.locks
    .request(LOCK_NAME, { steal }, () => {
      setLeader(true);
      // Hold the lock until this tab dies — intentionally never resolves.
      return new Promise<never>(() => {});
    })
    .catch(() => {
      // Another tab stole the lock (AbortError): become a remote control
      // and wait in line for the next turn.
      setLeader(false);
      holdLock(false);
    });
}

export function startAudioLeaderElection(onLeaderChange: (isLeader: boolean) => void): void {
  notifyLeader = onLeaderChange;
  // No Web Locks (ancient browser, jsdom in tests): single-tab behavior.
  if (typeof navigator === 'undefined' || navigator.locks === undefined) {
    setLeader(true);
    return;
  }
  setLeader(false);
  holdLock(false);
}

/**
 * Take audio ownership for this tab, but only from a real user gesture —
 * programmatic plays (WebSocket commands reach every tab) must not make tabs
 * fight over the lock.
 */
export function claimAudioLeadership(): void {
  if (isLeader || typeof navigator === 'undefined' || navigator.locks === undefined) return;
  if (!navigator.userActivation?.isActive) return;
  holdLock(true);
}
