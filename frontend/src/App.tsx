import { useEffect, useState } from "react";

type BackendStatus = "checking" | "connected" | "disconnected";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");

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
    <main style={{ padding: "3rem", textAlign: "center" }}>
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
    </main>
  );
}

export default App;
