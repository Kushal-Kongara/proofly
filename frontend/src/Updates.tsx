import { useEffect, useState } from "react";
import { ApiError, ImmigrationUpdateResult, UpdateCategory, UpdateTimeRange, UpdatesResponse, getUpdates } from "./api/updates";
import { formatDateOnly } from "./lib/date";
import "./Updates.css";

const CATEGORY_OPTIONS: { value: UpdateCategory; label: string }[] = [
  { value: "f1_opt", label: "F-1 / OPT" },
  { value: "o1a", label: "O-1A Extraordinary" },
  { value: "general", label: "General USCIS Policy" },
];

const TIME_RANGE_OPTIONS: { value: UpdateTimeRange; label: string }[] = [
  { value: "month", label: "Past Month" },
  { value: "year", label: "Past Year" },
];

function ResultCard({ result, isPriority }: { result: ImmigrationUpdateResult; isPriority: boolean }) {
  return (
    <div className={`updates-card${isPriority ? " updates-card--priority" : ""}`}>
      <div className="updates-card-header">
        <div className="updates-card-badges">
          {isPriority && (
            <span className="updates-priority-badge">
              ⚡ PRIORITY NEWS
            </span>
          )}
          <span className="updates-domain-badge">{result.official_domain}</span>
        </div>
        {result.published_date && <span className="updates-date">{formatDateOnly(result.published_date)}</span>}
      </div>
      <h3 className="updates-card-title">{result.title}</h3>
      <p className="updates-card-snippet">{result.snippet}</p>
      <a className="updates-card-link" href={result.url} target="_blank" rel="noopener noreferrer">
        Open official source ↗
      </a>
    </div>
  );
}

export default function Updates() {
  const [category, setCategory] = useState<UpdateCategory>("general");
  const [timeRange, setTimeRange] = useState<UpdateTimeRange>("year");
  const [response, setResponse] = useState<UpdatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMessage(null);

    getUpdates(category, timeRange)
      .then((result) => {
        if (!cancelled) setResponse(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setResponse(null);
          setErrorMessage(err instanceof ApiError ? err.message : "Could not load official updates.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [category, timeRange]);

  return (
    <section className="updates-page">
      <div className="updates-header">
        <div>
          <h2>Official Policy Radar</h2>
          <p className="updates-subtitle">Real-time official US government immigration notices strictly from USCIS, ICE, and State.gov</p>
        </div>
        <span className="updates-official-only-badge">Verified Government Sources Only</span>
      </div>

      <div className="updates-controls">
        <div className="updates-control-group">
          {CATEGORY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`updates-control-btn${category === option.value ? " updates-control-btn--active" : ""}`}
              onClick={() => setCategory(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="updates-control-group">
          {TIME_RANGE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`updates-control-btn${timeRange === option.value ? " updates-control-btn--active" : ""}`}
              onClick={() => setTimeRange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="updates-status updates-status--loading">Searching official government repositories…</p>}
      {errorMessage && <p className="updates-status updates-status--error">{errorMessage}</p>}

      {!loading && !errorMessage && response && (
        <>
          <div className="updates-meta-row">
            <span>Last checked: {new Date(response.retrieved_at).toLocaleString()}</span>
            {response.cache_hit && <span className="updates-cached-badge">Cached result</span>}
          </div>

          {response.results.length === 0 ? (
            <p className="updates-empty">No official results found for this category and time range.</p>
          ) : (
            <div className="updates-results">
              {response.results.map((result, idx) => (
                <ResultCard result={result} key={result.id} isPriority={idx === 0} />
              ))}
            </div>
          )}

          <p className="legal-disclaimer">{response.disclaimer}</p>
        </>
      )}
    </section>
  );
}
