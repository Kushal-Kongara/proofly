import { describe, expect, it } from "vitest";
import { formatDateOnly, parseDateOnly } from "./date";

// process.env.TZ is set to America/Los_Angeles in vite.config.ts's test
// config for this exact reason: proves the bug (new Date("YYYY-MM-DD")
// interpreted as UTC midnight, then rendered in a UTC-behind timezone)
// cannot recur, rather than merely not reproducing it by accident.
describe("formatDateOnly", () => {
  it("displays 2027-06-30 as June 30, 2027", () => {
    expect(formatDateOnly("2027-06-30")).toBe("June 30, 2027");
  });

  it("displays 2024-05-18 as May 18, 2024", () => {
    expect(formatDateOnly("2024-05-18")).toBe("May 18, 2024");
  });

  it("displays 2026-09-05 as September 5, 2026", () => {
    expect(formatDateOnly("2026-09-05")).toBe("September 5, 2026");
  });

  it("does not depend on the America/Los_Angeles timezone", () => {
    expect(process.env.TZ).toBe("America/Los_Angeles");

    // The historical bug: new Date("2027-06-30T00:00:00Z") is UTC
    // midnight, which is June 29 in Pacific Time — confirm that
    // failure mode is real in this environment, then confirm our
    // util doesn't exhibit it.
    const naiveUtcMidnight = new Date("2027-06-30T00:00:00Z");
    expect(naiveUtcMidnight.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })).toBe(
      "June 29, 2027",
    );

    expect(formatDateOnly("2027-06-30")).toBe("June 30, 2027");
  });

  it("returns an em dash for null/undefined/empty", () => {
    expect(formatDateOnly(null)).toBe("—");
    expect(formatDateOnly(undefined)).toBe("—");
    expect(formatDateOnly("")).toBe("—");
  });

  it("returns the raw value unchanged for a non-date-only string", () => {
    expect(formatDateOnly("not-a-date")).toBe("not-a-date");
    expect(formatDateOnly("2027-06-30T00:00:00Z")).toBe("2027-06-30T00:00:00Z");
  });

  it("supports custom Intl.DateTimeFormat options", () => {
    expect(formatDateOnly("2026-09-05", { year: "numeric", month: "short", day: "numeric" })).toBe("Sep 5, 2026");
  });
});

describe("parseDateOnly", () => {
  it("parses YYYY-MM-DD into a Date whose UTC fields match the input exactly", () => {
    const parsed = parseDateOnly("2027-06-30");
    expect(parsed).not.toBeNull();
    expect(parsed!.getUTCFullYear()).toBe(2027);
    expect(parsed!.getUTCMonth()).toBe(5); // 0-indexed
    expect(parsed!.getUTCDate()).toBe(30);
  });

  it("returns null for invalid input", () => {
    expect(parseDateOnly("not-a-date")).toBeNull();
    expect(parseDateOnly("2027-06-30T00:00:00Z")).toBeNull();
    expect(parseDateOnly("06/30/2027")).toBeNull();
  });
});
