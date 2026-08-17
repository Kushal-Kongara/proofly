import { describe, expect, it, vi } from "vitest";
import { isBackendReady, pollBackendHealth } from "./backendHealth";

/** A fake clock — advances only when `sleep` is awaited, never in real time. */
function fakeClock() {
  let elapsed = 0;
  return {
    now: () => elapsed,
    sleep: async (ms: number) => {
      elapsed += ms;
    },
  };
}

describe("pollBackendHealth", () => {
  it("resolves true immediately on the first successful attempt", async () => {
    const attempt = vi.fn().mockResolvedValue(true);
    const { now, sleep } = fakeClock();

    const result = await pollBackendHealth({
      attempt,
      deadlineMs: 90_000,
      retryDelayMs: 2_000,
      isCancelled: () => false,
      sleep,
      now,
    });

    expect(result).toBe(true);
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("retries after an initial failure and succeeds on the next attempt", async () => {
    const attempt = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    const { now, sleep } = fakeClock();
    const sleepSpy = vi.fn(sleep);

    const result = await pollBackendHealth({
      attempt,
      deadlineMs: 90_000,
      retryDelayMs: 2_000,
      isCancelled: () => false,
      sleep: sleepSpy,
      now,
    });

    expect(result).toBe(true);
    expect(attempt).toHaveBeenCalledTimes(2);
    expect(sleepSpy).toHaveBeenCalledTimes(1);
    expect(sleepSpy).toHaveBeenCalledWith(2_000);
  });

  it("never overlaps attempts — the next attempt only starts after the previous one settles", async () => {
    let inFlight = 0;
    let maxConcurrent = 0;
    let calls = 0;

    const attempt = vi.fn(async () => {
      inFlight += 1;
      maxConcurrent = Math.max(maxConcurrent, inFlight);
      calls += 1;
      // Yield a couple of microtask turns to give a buggy caller a chance
      // to start an overlapping attempt before this one resolves.
      await Promise.resolve();
      await Promise.resolve();
      inFlight -= 1;
      return calls >= 4; // succeed on the 4th attempt
    });
    const { now, sleep } = fakeClock();

    const result = await pollBackendHealth({
      attempt,
      deadlineMs: 90_000,
      retryDelayMs: 1_000,
      isCancelled: () => false,
      sleep,
      now,
    });

    expect(result).toBe(true);
    expect(attempt).toHaveBeenCalledTimes(4);
    expect(maxConcurrent).toBe(1);
  });

  it("stops retrying once the deadline elapses and resolves false", async () => {
    const attempt = vi.fn().mockResolvedValue(false);
    const { now, sleep } = fakeClock();

    const result = await pollBackendHealth({
      attempt,
      deadlineMs: 10_000,
      retryDelayMs: 3_000,
      isCancelled: () => false,
      sleep,
      now,
    });

    expect(result).toBe(false);
    // start=0; attempts fire at t=0,3000,6000,9000 (each still under the
    // 10s deadline, so each is followed by a sleep), then one final attempt
    // at t=12000, whose deadline check (12000 >= 10000) finally stops the
    // loop. A bounded, small number of attempts either way — never runaway.
    expect(attempt.mock.calls.length).toBeGreaterThanOrEqual(4);
    expect(attempt.mock.calls.length).toBeLessThan(10);
  });

  it("stops immediately once isCancelled() is true, without waiting out the deadline", async () => {
    const attempt = vi.fn().mockResolvedValue(false);
    const { now, sleep } = fakeClock();

    const result = await pollBackendHealth({
      attempt,
      deadlineMs: 90_000,
      retryDelayMs: 1_000,
      isCancelled: () => true,
      sleep,
      now,
    });

    expect(result).toBe(false);
    expect(attempt).not.toHaveBeenCalled();
  });

  it("a fresh call starts a full new deadline window — a manual retry is not cut short by a prior cycle", async () => {
    const clock = fakeClock();
    const failingAttempt = vi.fn().mockResolvedValue(false);

    // First cycle: exhausts the full 10s deadline and gives up.
    const firstResult = await pollBackendHealth({
      attempt: failingAttempt,
      deadlineMs: 10_000,
      retryDelayMs: 5_000,
      isCancelled: () => false,
      sleep: clock.sleep,
      now: clock.now,
    });
    expect(firstResult).toBe(false);
    const elapsedAfterFirstCycle = clock.now();
    expect(elapsedAfterFirstCycle).toBeGreaterThanOrEqual(10_000);

    // Manual retry: a second, independent call — succeeds on its first
    // attempt, proving it isn't judged against the first cycle's already
    // "spent" 10s+ of elapsed clock time.
    const succeedingAttempt = vi.fn().mockResolvedValue(true);
    const secondResult = await pollBackendHealth({
      attempt: succeedingAttempt,
      deadlineMs: 10_000,
      retryDelayMs: 5_000,
      isCancelled: () => false,
      sleep: clock.sleep,
      now: clock.now,
    });

    expect(secondResult).toBe(true);
    expect(succeedingAttempt).toHaveBeenCalledTimes(1);
  });
});

describe("isBackendReady", () => {
  it("is true only for the connected status", () => {
    expect(isBackendReady("connected")).toBe(true);
    expect(isBackendReady("checking")).toBe(false);
    expect(isBackendReady("unavailable")).toBe(false);
  });
});
