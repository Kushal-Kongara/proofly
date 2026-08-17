/**
 * Parses VITE_DEMO_READ_ONLY (Phase 7B). Vite env vars are always strings
 * (or undefined), so this is an explicit, case-insensitive "true" check —
 * anything else (undefined, "false", "1", "") is not-read-only, matching
 * local development's default.
 */

export interface DemoReadOnlyEnv {
  VITE_DEMO_READ_ONLY?: string;
}

export function resolveDemoReadOnly(env: DemoReadOnlyEnv): boolean {
  return env.VITE_DEMO_READ_ONLY?.toLowerCase() === "true";
}
