import { describe, expect, it } from "vitest";
import { resolveDemoAllowUploads } from "./resolveDemoAllowUploads";

describe("resolveDemoAllowUploads", () => {
  it("defaults to false when unset", () => {
    expect(resolveDemoAllowUploads({})).toBe(false);
  });

  it("is true for the literal string 'true'", () => {
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "true" })).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "True" })).toBe(true);
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "TRUE" })).toBe(true);
  });

  it("is false for any other value", () => {
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "false" })).toBe(false);
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "1" })).toBe(false);
    expect(resolveDemoAllowUploads({ VITE_DEMO_ALLOW_UPLOADS: "" })).toBe(false);
  });
});
