/**
 * Parses VITE_DEMO_ALLOW_UPLOADS (Phase 7D). Same case-insensitive "true"
 * check as resolveDemoReadOnly — anything else (undefined, "false", "1",
 * "") is not-allowed. Only meaningful when VITE_DEMO_READ_ONLY is also
 * true; see client.ts's UPLOAD_BLOCKED.
 */

export interface DemoAllowUploadsEnv {
  VITE_DEMO_ALLOW_UPLOADS?: string;
}

export function resolveDemoAllowUploads(env: DemoAllowUploadsEnv): boolean {
  return env.VITE_DEMO_ALLOW_UPLOADS?.toLowerCase() === "true";
}
