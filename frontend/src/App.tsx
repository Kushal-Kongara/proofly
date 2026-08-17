import { useCallback, useEffect, useRef, useState } from "react";
import type { BackendStatus } from "./api/backendHealth";
import { createHealthCheckAttempt, isBackendReady, pollBackendHealth } from "./api/backendHealth";
import { API_BASE_URL, DEMO_READ_ONLY } from "./api/client";
import Chat from "./Chat";
import ChatbotDrawer from "./ChatbotDrawer";
import Dashboard from "./Dashboard";
import DocumentVault from "./DocumentVault";
import LandingPage from "./LandingPage";
import O1Plan from "./O1Plan";
import Updates from "./Updates";

type ViewMode = "landing" | "app";
type Page = "dashboard" | "documents" | "o1plan" | "chat" | "updates";

const HEALTH_CHECK_PER_ATTEMPT_TIMEOUT_MS = 5_000;
const HEALTH_CHECK_RETRY_DELAY_MS = 2_000;
const HEALTH_CHECK_DEADLINE_MS = 90_000;

const ENGAGING_FACTS = [
  "💡 Did you know? O-1A extraordinary talent visas have no annual lottery cap and allow unlimited extensions.",
  "💡 STEM OPT grants an extra 24 months of US work authorization for qualifying STEM degree graduates.",
  "💡 F-1 students receive a 60-day grace period post-OPT to transition to H-1B, O-1A, or new status.",
  "💡 Peer review judging invitations & journal paper referee letters strongly support the O-1A Judging criterion.",
  "💡 An I-94 showing 'D/S' stands for Duration of Status — valid as long as your SEVIS & OPT remains active.",
  "💡 Proofly grounds every answer strictly in your real uploaded documents with zero AI hallucinations."
];

function StartingScreen() {
  const [factIndex, setFactIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setFactIndex((prev) => (prev + 1) % ENGAGING_FACTS.length);
    }, 3800);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="backend-boot-screen">
      <div className="backend-boot-card">
        <div className="backend-boot-spinner" aria-hidden="true" />
        <h1 className="backend-boot-title">Starting Proofly…</h1>
        <p className="backend-boot-sub">Connecting to server & loading preloaded Maya Patel synthetic profile...</p>

        <div className="backend-boot-fact-box">
          <span className="backend-boot-fact-label">IMMIGRATION FACT</span>
          <p className="backend-boot-fact-text">{ENGAGING_FACTS[factIndex]}</p>
        </div>
      </div>
    </main>
  );
}

function UnavailableScreen({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="backend-boot-screen">
      <div className="backend-boot-card">
        <h1 className="backend-boot-title">Proofly is unavailable right now</h1>
        <p className="backend-boot-sub">The backend didn't respond in time. It may still be starting up — try again in a moment.</p>
        <button type="button" className="backend-boot-retry-btn" onClick={onRetry}>
          Retry connection
        </button>
      </div>
    </main>
  );
}

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [viewMode, setViewMode] = useState<ViewMode>("landing");
  const [page, setPage] = useState<Page>("dashboard");

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
      if (cycleRef.current !== cycleId) return;
      setStatus(succeeded ? "connected" : "unavailable");
    });
  }, []);

  useEffect(() => {
    startHealthCheckCycle();
    return () => {
      cycleRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isBackendReady(status)) {
    return status === "checking" ? <StartingScreen /> : <UnavailableScreen onRetry={startHealthCheckCycle} />;
  }

  const handleEnterApp = (targetPage?: Page) => {
    if (targetPage) {
      setPage(targetPage);
    }
    setViewMode("app");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (viewMode === "landing") {
    return <LandingPage onEnterApp={handleEnterApp} />;
  }

  return (
    <div className="app-root-wrapper">
      {DEMO_READ_ONLY && (
        <div className="demo-banner" role="note">
          <span className="demo-banner-badge">Public demo</span>
          <span>
            Preloaded with Maya Patel synthetic documents (F-1 → OPT → STEM OPT → O-1A profile).
          </span>
        </div>
      )}

      {/* Top Application Header matching Home Page style */}
      <header className="app-header-bar">
        <div className="app-header-container">
          <button type="button" className="app-logo-brand" onClick={() => setViewMode("landing")}>
            <span className="app-logo-serif">Proofly</span>
          </button>

          <nav className="app-nav-pills">
            <button
              type="button"
              className={`app-nav-pill${page === "dashboard" ? " app-nav-pill--active" : ""}`}
              onClick={() => setPage("dashboard")}
            >
              Dashboard
            </button>
            <button
              type="button"
              className={`app-nav-pill${page === "documents" ? " app-nav-pill--active" : ""}`}
              onClick={() => setPage("documents")}
            >
              Document Vault
            </button>
            <button
              type="button"
              className={`app-nav-pill${page === "o1plan" ? " app-nav-pill--active" : ""}`}
              onClick={() => setPage("o1plan")}
            >
              O-1 Scorecard
            </button>
            <button
              type="button"
              className={`app-nav-pill${page === "chat" ? " app-nav-pill--active" : ""}`}
              onClick={() => setPage("chat")}
            >
              Ask Proofly AI
            </button>
            <button
              type="button"
              className={`app-nav-pill${page === "updates" ? " app-nav-pill--active" : ""}`}
              onClick={() => setPage("updates")}
            >
              Official Updates
            </button>
          </nav>

          <div className="app-header-actions">
            <button
              type="button"
              className="app-landing-btn"
              onClick={() => setViewMode("landing")}
              title="Return to Landing Page"
            >
              <span>Home</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="app-main-content">
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

      {/* Global Floating Chatbot Drawer */}
      <ChatbotDrawer />
    </div>
  );
}

export default App;
