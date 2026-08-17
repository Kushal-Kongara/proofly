/**
 * Cold-start health polling (Phase 7C). The free-tier Render backend can
 * take up to ~60s to wake from an idle spin-down, so a single /health call
 * on page load isn't enough — App.tsx needs to retry sequentially for a
 * bounded window before either rendering the app or giving up.
 *
 * Split into two pieces so the retry/timing logic (the part with real bugs
 * to get wrong — overlap, runaway retries, an un-resettable deadline) is a
 * pure function testable without a real fetch, timers, or a DOM:
 * - `pollBackendHealth` — sequencing only: retry a supplied `attempt()`
 *   until it succeeds or `deadlineMs` elapses, one attempt at a time.
 * - `createHealthCheckAttempt` — the one real-fetch attempt, with its own
 *   per-attempt timeout via AbortController. Never rejects — a network
 *   error or timeout is just a failed attempt, not a thrown error, so
 *   `pollBackendHealth` never needs a try/catch of its own.
 */

export type BackendStatus = "checking" | "connected" | "unavailable";

export function isBackendReady(status: BackendStatus): status is "connected" {
  return status === "connected";
}

export interface PollBackendHealthOptions {
  /** One health-check attempt. Must resolve (never reject) — true if healthy. */
  attempt: () => Promise<boolean>;
  /** Total time budget across every attempt, measured from the first call. */
  deadlineMs: number;
  /** Delay between a failed attempt and the next one. */
  retryDelayMs: number;
  /** Checked before every attempt and before every wait — lets a caller
   * (e.g. a React effect's cleanup on unmount) stop an in-flight cycle. */
  isCancelled: () => boolean;
  /** Injectable so tests never wait in real time. Defaults to a real timer. */
  sleep?: (ms: number) => Promise<void>;
  /** Injectable clock, defaults to Date.now. */
  now?: () => number;
}

const realSleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Sequentially retries `attempt()` — strictly one call in flight at a time,
 * since each call is `await`ed before the next is even constructed — until
 * it resolves true, or `deadlineMs` has elapsed since the first attempt.
 * Every call starts its own fresh deadline window; nothing here is shared
 * state, so calling this again (e.g. from a "Retry connection" button)
 * always gets the full `deadlineMs` again.
 */
export async function pollBackendHealth(options: PollBackendHealthOptions): Promise<boolean> {
  const { attempt, deadlineMs, retryDelayMs, isCancelled, sleep = realSleep, now = Date.now } = options;
  const start = now();

  while (!isCancelled()) {
    const ok = await attempt();
    if (ok) return true;
    if (isCancelled()) return false;
    if (now() - start >= deadlineMs) return false;
    await sleep(retryDelayMs);
  }

  return false;
}

/**
 * Builds one real /health attempt against `baseUrl`, aborted after
 * `timeoutMs` so a hung request can't stall the retry loop past its own
 * per-attempt budget. Never throws — any failure (network error, non-OK
 * status, timeout, bad JSON) resolves false.
 */
export function createHealthCheckAttempt(baseUrl: string, timeoutMs: number): () => Promise<boolean> {
  return async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${baseUrl}/health`, { signal: controller.signal });
      if (!response.ok) return false;
      const data = await response.json();
      return data?.status === "ok";
    } catch {
      return false;
    } finally {
      clearTimeout(timeoutId);
    }
  };
}
