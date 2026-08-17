import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { MISSING_API_BASE_URL_MESSAGE } from "./src/api/resolveApiBaseUrl";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // A production build with no VITE_API_BASE_URL would otherwise silently
  // ship a bundle that falls back to http://localhost:8000 in the deployed
  // frontend — fail the build itself, loudly, instead. Dev server runs
  // (`vite`/`vite dev`) are unaffected; they keep the localhost fallback in
  // src/api/resolveApiBaseUrl.ts.
  if (command === "build" && mode === "production" && !env.VITE_API_BASE_URL) {
    throw new Error(MISSING_API_BASE_URL_MESSAGE);
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
    },
  };
});
