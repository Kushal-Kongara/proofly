import { describe, expect, it } from "vitest";
import { MISSING_API_BASE_URL_MESSAGE, resolveApiBaseUrl } from "./resolveApiBaseUrl";

describe("resolveApiBaseUrl", () => {
  it("uses VITE_API_BASE_URL when set, regardless of DEV", () => {
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: "https://api.proofly.example", DEV: false })).toBe(
      "https://api.proofly.example",
    );
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: "https://api.proofly.example", DEV: true })).toBe(
      "https://api.proofly.example",
    );
  });

  it("falls back to localhost only in dev mode", () => {
    expect(resolveApiBaseUrl({ DEV: true })).toBe("http://localhost:8000");
  });

  it("throws instead of silently falling back to localhost outside dev", () => {
    expect(() => resolveApiBaseUrl({ DEV: false })).toThrow(MISSING_API_BASE_URL_MESSAGE);
  });

  it("throws when VITE_API_BASE_URL is an empty string outside dev", () => {
    expect(() => resolveApiBaseUrl({ VITE_API_BASE_URL: "", DEV: false })).toThrow(MISSING_API_BASE_URL_MESSAGE);
  });
});
