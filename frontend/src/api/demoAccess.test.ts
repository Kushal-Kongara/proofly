import { describe, expect, it } from "vitest";
import { isDeleteBlocked, isUploadBlocked } from "./demoAccess";

describe("isUploadBlocked", () => {
  it("is false outside the public demo, regardless of the allow-uploads flag", () => {
    expect(isUploadBlocked(false, false)).toBe(false);
    expect(isUploadBlocked(false, true)).toBe(false);
  });

  it("is true in the public demo unless uploads are explicitly allowed", () => {
    expect(isUploadBlocked(true, false)).toBe(true);
  });

  it("is false in the public demo when uploads are explicitly allowed", () => {
    expect(isUploadBlocked(true, true)).toBe(false);
  });
});

describe("isDeleteBlocked", () => {
  it("is true whenever the public demo is on — no allow-uploads carve-out for delete", () => {
    expect(isDeleteBlocked(true)).toBe(true);
  });

  it("is false outside the public demo", () => {
    expect(isDeleteBlocked(false)).toBe(false);
  });
});
