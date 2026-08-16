import { useEffect, useState } from "react";
import Chat from "./Chat";
import Dashboard from "./Dashboard";
import DocumentVault from "./DocumentVault";
import O1Plan from "./O1Plan";

type BackendStatus = "checking" | "connected" | "disconnected";
type Page = "dashboard" | "documents" | "o1plan" | "chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [page, setPage] = useState<Page>("dashboard");

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE_URL}/health`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (!cancelled) {
          setStatus(data?.status === "ok" ? "connected" : "disconnected");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("disconnected");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <header style={{ padding: "3rem 1.5rem 0", textAlign: "center" }}>
        <h1>Proofly</h1>
        <p>Immigration clarity, grounded in your documents</p>
        <p>
          Backend status:{" "}
          <strong>
            {status === "checking" && "checking..."}
            {status === "connected" && "connected"}
            {status === "disconnected" && "disconnected"}
          </strong>
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
    </main>
  );
}

export default App;
