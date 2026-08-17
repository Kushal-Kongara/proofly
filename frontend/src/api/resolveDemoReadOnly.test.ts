import { describe, expect, it } from "vitest";
import { resolveDemoReadOnly } from "./resolveDemoReadOnly";

describe("resolveDemoReadOnly", () => {
  it("defaults to false when unset", () => {
    expect(resolveDemoReadOnly({})).toBe(false);
  });

  it("is true for the literal string 'true'", () => {
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "true" })).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "True" })).toBe(true);
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "TRUE" })).toBe(true);
  });

  it("is false for any other value", () => {
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "false" })).toBe(false);
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "1" })).toBe(false);
    expect(resolveDemoReadOnly({ VITE_DEMO_READ_ONLY: "" })).toBe(false);
  });
});
