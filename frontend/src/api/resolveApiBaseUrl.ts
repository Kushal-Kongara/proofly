/**
 * Single source of truth for turning `VITE_API_BASE_URL` (plus the current
 * Vite mode) into the backend base URL — used both at runtime (`client.ts`,
 * via `import.meta.env`) and at build time (`vite.config.ts`, via
 * `loadEnv`), so there is exactly one place that decides when it's safe to
 * fall back to `http://localhost:8000`.
 *
 * Falling back to localhost is only ever safe in local dev. A production
 * build/run with no `VITE_API_BASE_URL` set must fail loudly instead of
 * silently shipping a frontend that talks to `localhost:8000` — pointing a
 * deployed frontend at a URL that doesn't exist there is a hard-to-diagnose
 * "everything is broken" bug, not a graceful degradation.
 */

export const MISSING_API_BASE_URL_MESSAGE =
  "VITE_API_BASE_URL is required outside local development — refusing to " +
  "fall back to http://localhost:8000 in a production build.";

const LOCAL_DEV_API_BASE_URL = "http://localhost:8000";

export interface ApiBaseUrlEnv {
  VITE_API_BASE_URL?: string;
  DEV?: boolean;
}

export function resolveApiBaseUrl(env: ApiBaseUrlEnv): string {
  if (env.VITE_API_BASE_URL) {
    return env.VITE_API_BASE_URL;
  }
  if (env.DEV) {
    return LOCAL_DEV_API_BASE_URL;
  }
  throw new Error(MISSING_API_BASE_URL_MESSAGE);
}
