import { useCallback, useEffect, useRef, useState } from "react";
import type { BackendStatus } from "./api/backendHealth";
import { createHealthCheckAttempt, isBackendReady, pollBackendHealth } from "./api/backendHealth";
import { API_BASE_URL, DEMO_READ_ONLY } from "./api/client";
import Chat from "./Chat";
import Dashboard from "./Dashboard";
import DocumentVault from "./DocumentVault";
import O1Plan from "./O1Plan";
import Updates from "./Updates";

type Page = "dashboard" | "documents" | "o1plan" | "chat" | "updates";

// The free-tier deployment can take up to ~60s to wake from an idle
// spin-down — see docs/DEPLOYMENT.md's "Cold-start experience" section.
const HEALTH_CHECK_PER_ATTEMPT_TIMEOUT_MS = 5_000;
const HEALTH_CHECK_RETRY_DELAY_MS = 2_000;
const HEALTH_CHECK_DEADLINE_MS = 90_000;

function StartingScreen() {
  return (
    <main className="backend-boot-screen">
      <div className="backend-boot-card">
        <div className="backend-boot-spinner" aria-hidden="true" />
        <h1>Starting Proofly…</h1>
        <p>The public demo server may take up to a minute to wake up.</p>
      </div>
    </main>
  );
}

function UnavailableScreen({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="backend-boot-screen">
      <div className="backend-boot-card">
        <h1>Proofly is unavailable right now</h1>
        <p>The backend didn't respond in time. It may still be starting up — try again in a moment.</p>
        <button type="button" className="backend-boot-retry-btn" onClick={onRetry}>
          Retry connection
        </button>
      </div>
    </main>
  );
}

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [page, setPage] = useState<Page>("dashboard");

  // A cycle counter, not just a single cancelled flag: a manual retry
  // starts a new cycle while an old one's in-flight attempt may still be
  // pending — this lets that stale cycle's eventual result be ignored
  // instead of racing with (and possibly overwriting) the new one's.
  const cycleRef = useRef(0);

  const startHealthCheckCycle = useCallback(() => {
    const cycleId = ++cycleRef.current;
    setStatus("checking");

    pollBackendHealth({
      attempt: createHealthCheckAttempt(API_BASE_URL, HEALTH_CHECK_PER_ATTEMPT_TIMEOUT_MS),
      deadlineMs: HEALTH_CHECK_DEADLINE_MS,
      retryDelayMs: HEALTH_CHECK_RETRY_DELAY_MS,
      isCancelled: () => cycleRef.current !== cycleId,
    }).then((succeeded) => {
      if (cycleRef.current !== cycleId) return; // superseded by a newer cycle or unmount
      setStatus(succeeded ? "connected" : "unavailable");
    });
  }, []);

  useEffect(() => {
    startHealthCheckCycle();
    return () => {
      // Bump past whatever cycle is running so its eventual result is
      // ignored — there's no separate "unmounted" state to track.
      cycleRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isBackendReady(status)) {
    return status === "checking" ? <StartingScreen /> : <UnavailableScreen onRetry={startHealthCheckCycle} />;
  }

  // Feature pages (Dashboard, Documents, O-1 Plan, Chat, Updates) are only
  // ever mounted once /health has actually succeeded — each of them fires
  // its own request(s) on mount, which would otherwise hit a sleeping
  // backend on every cold-start page load.
  return (
    <main>
      {DEMO_READ_ONLY && (
        <div className="demo-banner" role="note">
          <span className="demo-banner-badge">Public demo</span>
          <span>
            This deployment uses preloaded synthetic documents only. Uploads and deletions are
            disabled here to keep the shared demo data intact for every visitor.
          </span>
        </div>
      )}

      <header style={{ padding: "3rem 1.5rem 0", textAlign: "center" }}>
        <h1>Proofly</h1>
        <p>Immigration clarity, grounded in your documents</p>
        <p>
          Backend status: <strong>connected</strong>
        </p>
      </header>

      <nav className="app-nav">
        <button
          type="button"
          className={`app-nav-btn${page === "dashboard" ? " app-nav-btn--active" : ""}`}
          onClick={() => setPage("dashboard")}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`app-nav-btn${page === "documents" ? " app-nav-btn--active" : ""}`}
          onClick={() => setPage("documents")}
        >
          Documents
        </button>
        <button
          type="button"
          className={`app-nav-btn${page === "o1plan" ? " app-nav-btn--active" : ""}`}
          onClick={() => setPage("o1plan")}
        >
          O-1 Plan
        </button>
        <button
          type="button"
          className={`app-nav-btn${page === "chat" ? " app-nav-btn--active" : ""}`}
          onClick={() => setPage("chat")}
        >
          Ask Proofly
        </button>
        <button
          type="button"
          className={`app-nav-btn${page === "updates" ? " app-nav-btn--active" : ""}`}
          onClick={() => setPage("updates")}
        >
          Official Updates
        </button>
      </nav>

      <div style={{ display: page === "dashboard" ? "block" : "none" }}>
        <Dashboard />
      </div>
      <div style={{ display: page === "documents" ? "block" : "none" }}>
        <DocumentVault />
      </div>
      <div style={{ display: page === "o1plan" ? "block" : "none" }}>
        <O1Plan />
      </div>
      <div style={{ display: page === "chat" ? "block" : "none" }}>
        <Chat />
      </div>
      <div style={{ display: page === "updates" ? "block" : "none" }}>
        <Updates />
      </div>
    </main>
  );
}

export default App;
