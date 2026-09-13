/**
 * Cross-tab audio leader election via the Web Locks API.
 *
 * Every same-origin tab shares one persisted device-id, so the backend sees
 * them as a single device — but each tab owns its own <audio> elements. Only
 * the tab holding this lock may drive audio; the rest act as remote controls
 * (the same code path used when another device is active). The browser
 * releases the lock automatically when the holding tab closes or crashes,
 * promoting the longest-waiting tab — no heartbeats, no cleanup handlers.
 */
const LOCK_NAME = 'music-minion-audio-leader';

export function startAudioLeaderElection(setLeader: (isLeader: boolean) => void): void {
  // No Web Locks (ancient browser, jsdom in tests): single-tab behavior.
  if (typeof navigator === 'undefined' || navigator.locks === undefined) {
    setLeader(true);
    return;
  }
  setLeader(false);
  void navigator.locks.request(LOCK_NAME, () => {
    setLeader(true);
    // Hold the lock until this tab dies — intentionally never resolves.
    return new Promise<never>(() => {});
  });
}
