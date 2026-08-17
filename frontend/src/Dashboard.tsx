import { useCallback, useEffect, useState } from "react";
import {
  AnalysisResult,
  ApiError,
  EmploymentAuthorizationRecord,
  ImmigrationClassification,
  TimelineAnalysisEvent,
  TimelineEventCategory,
  getLatestAnalysis,
  runAnalysis,
} from "./api/analysis";
import { VaultDocument, listDocuments } from "./api/documents";
import { formatDateOnly } from "./lib/date";
import "./Dashboard.css";

const CLASSIFICATION_LABELS: Record<ImmigrationClassification, string> = {
  f1: "F-1 Student",
  h1b: "H-1B Specialty",
  o1a: "O-1A Extraordinary",
  other: "Other Status",
};

const CATEGORY_LABELS: Record<TimelineEventCategory, string> = {
  work_authorization: "Work authorization",
  visa_validity: "Visa validity",
  academic_program: "Academic program",
  passport: "Passport",
  status: "Immigration status",
  other: "Other",
};

function daysRemainingLabel(days: number | null, status: TimelineAnalysisEvent["status"]): string {
  if (days === null) return "Duration of Status (D/S)";
  if (status === "historical") return `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  if (days < 0) return `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}`;
  if (days === 0) return "Due today";
  return `${days} day${days === 1 ? "" : "s"} remaining`;
}

const ANALYSIS_LOADING_FACTS: string[] = [
  "F-1 students get a 60-day grace period after their program end date to leave the US, transfer, or change status.",
  "Post-completion OPT gives F-1 students up to 12 months of work authorization tied to their degree field.",
  "STEM OPT extensions add up to 24 additional months for graduates in eligible science, tech, engineering, or math majors.",
  "An H-1B visa is initially granted for up to 3 years and can be extended to a maximum of 6 years in most cases.",
  "The O-1A visa has no maximum duration cap — it can be renewed indefinitely in 1-year increments.",
  "An I-94 arrival record, not the visa stamp, is what actually governs how long you're authorized to stay in the US.",
  "'Duration of Status' (D/S) means your authorized stay is tied to maintaining student status, not a fixed date.",
  "A visa stamp's expiration date only controls travel and entry — it does not limit how long you may stay once admitted.",
  "The H-1B cap-gap rule can automatically extend F-1 status and work authorization while an H-1B change of status is pending.",
  "Unlike most visas, a 212(e) two-year home residency requirement can affect J-1 visa holders' ability to change status.",
];

function findCurrentAuthorization(
  authorizations: EmploymentAuthorizationRecord[],
  asOfDate: string,
): EmploymentAuthorizationRecord | null {
  const current = authorizations.filter((auth) => {
    const startsOk = !auth.start_date || auth.start_date <= asOfDate;
    const endsOk = !auth.end_date || auth.end_date >= asOfDate;
    return startsOk && endsOk;
  });
  if (current.length === 0) return null;
  return [...current].sort((a, b) => {
    if (!a.end_date) return -1;
    if (!b.end_date) return 1;
    return b.end_date.localeCompare(a.end_date);
  })[0];
}

export default function Dashboard() {
  const [documents, setDocuments] = useState<VaultDocument[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [factIndex, setFactIndex] = useState(0);

  useEffect(() => {
    if (!analyzing) return;
    setFactIndex(Math.floor(Math.random() * ANALYSIS_LOADING_FACTS.length));
    const interval = setInterval(() => {
      setFactIndex((prev) => (prev + 1) % ANALYSIS_LOADING_FACTS.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [analyzing]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [docsResponse, latestAnalysis] = await Promise.all([
        listDocuments(),
        getLatestAnalysis(),
      ]);
      setDocuments(docsResponse);
      setAnalysis(latestAnalysis);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    setErrorMessage(null);
    try {
      const result = await runAnalysis();
      setAnalysis(result);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Analysis run failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const activeAuth = analysis
    ? findCurrentAuthorization(analysis.employment_authorizations, analysis.as_of_date)
    : null;

  return (
    <div className="dashboard-root">
      {/* Welcome Top Header Bar */}
      <header className="dashboard-top-header">
        <div>
          <h2 className="dashboard-greeting-h2">Welcome Back, Maya Patel! 👋</h2>
          <p className="dashboard-greeting-sub">Here is your visa compliance & status breakdown today</p>
        </div>

        <div className="dashboard-header-actions">
          <div className="dashboard-date-pill">
            <span>📅 August 2026</span>
          </div>

          <button
            type="button"
            className="analyze-btn"
            onClick={handleRunAnalysis}
            disabled={analyzing || loading}
          >
            {analyzing ? "Running AI Analysis…" : "Run Document Analysis"}
          </button>
        </div>
      </header>

      {errorMessage && (
        <div className="dashboard-status dashboard-status--error">{errorMessage}</div>
      )}

      {analyzing && (
        <div className="analysis-loading-card" role="status" aria-live="polite">
          <div className="analysis-loading-spinner" />
          <div className="analysis-loading-body">
            <h3 className="analysis-loading-title">Running AI Analysis…</h3>
            <p className="analysis-loading-sub">
              Scanning your documents and cross-checking dates. Feel free to browse other tabs while this runs.
            </p>
            <div className="analysis-loading-fact">
              <span className="analysis-loading-fact-label">Did you know?</span>
              <p>{ANALYSIS_LOADING_FACTS[factIndex]}</p>
            </div>
          </div>
        </div>
      )}

      {/* 4 Summary Metric Cards Grid (Vendify style) */}
      <section className="summary-cards-grid">
        {/* Card 1: Active Status */}
        <div className="summary-card summary-card--highlight">
          <div className="summary-card-top-row">
            <span className="summary-card-label">CURRENT STATUS</span>
            <div className="summary-card-icon">🎓</div>
          </div>
          <div className="summary-card-value">
            {analysis?.reported_classification?.classification
              ? CLASSIFICATION_LABELS[analysis.reported_classification.classification]
              : "F-1 Student"}
          </div>
          <div className="summary-card-detail">
            {activeAuth ? activeAuth.authorization_type.replace(/_/g, " ").toUpperCase() : "Active Post-Completion OPT"}
          </div>
        </div>

        {/* Card 2: Expiration Countdown */}
        <div className="summary-card summary-card--blue">
          <div className="summary-card-top-row">
            <span className="summary-card-label">OPT EXPIRATION COUNTDOWN</span>
            <div className="summary-card-icon">⏱️</div>
          </div>
          <div className="summary-card-value">124 Days</div>
          <div className="summary-card-detail">Expires Dec 18, 2026</div>
        </div>

        {/* Card 3: STEM OPT */}
        <div className="summary-card summary-card--purple">
          <div className="summary-card-top-row">
            <span className="summary-card-label">STEM OPT EXTENSION</span>
            <div className="summary-card-icon">⚡</div>
          </div>
          <div className="summary-card-value">Eligible</div>
          <div className="summary-card-detail">24-Month Extension Verified</div>
        </div>

        {/* Card 4: Documents Parsed */}
        <div className="summary-card summary-card--cyan">
          <div className="summary-card-top-row">
            <span className="summary-card-label">DOCUMENT VAULT</span>
            <div className="summary-card-icon">📁</div>
          </div>
          <div className="summary-card-value">{documents.length} Docs</div>
          <div className="summary-card-detail">Vector indexed in Supermemory</div>
        </div>
      </section>

      {/* Split Main Content Area */}
      <div className="dashboard-main-split">
        {/* Left Column: Notices & Detailed Timeline */}
        <div>
          {analysis && (analysis.warnings.length > 0 || analysis.conflicts.length > 0) && (
            <div className="notices-group">
              {analysis.warnings.map((w, idx) => (
                <div key={`w-${idx}`} className="notice notice--warning">
                  {w.message}
                </div>
              ))}
              {analysis.conflicts.map((c, idx) => (
                <div key={`c-${idx}`} className="notice notice--conflict">
                  {c.description}
                </div>
              ))}
            </div>
          )}

          <div className="timeline-section">
            <h3 className="timeline-section-h3">Compliance & Expiration Timeline</h3>
            <p className="timeline-as-of">
              As of date: {analysis ? formatDateOnly(analysis.as_of_date) : "August 16, 2026"}
            </p>

            {loading ? (
              <div className="dashboard-status dashboard-status--loading">Loading timeline events…</div>
            ) : analysis && analysis.timeline.length > 0 ? (
              <div className="timeline-list">
                {analysis.timeline.map((event, idx) => (
                  <div key={`event-${idx}`} className={`timeline-row timeline-row--${event.status}`}>
                    <div className="timeline-row-main">
                      <span className="timeline-title">{event.title}</span>
                      <span className={`category-badge category-badge--${event.category}`}>
                        {CATEGORY_LABELS[event.category]}
                      </span>
                    </div>

                    <div className="timeline-row-detail">
                      <span>Date: {formatDateOnly(event.event_date)}</span>
                      <span className={`countdown--${event.status}`}>
                        {daysRemainingLabel(event.days_remaining, event.status)}
                      </span>
                    </div>

                    {event.explanation && (
                      <p className="timeline-explanation">{event.explanation}</p>
                    )}

                    <div className="timeline-source">Source: {event.source.document_id}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="dashboard-empty">No timeline events found. Run analysis to extract dates.</p>
            )}
          </div>
        </div>

        {/* Right Column: Widgets (Calendar & O-1 Readiness Ring) */}
        <div>
          {/* Mini Calendar Widget */}
          <div className="dashboard-widget-card">
            <div className="widget-title">
              <span>Compliance Calendar</span>
              <span style={{ fontSize: "0.8rem", color: "#64748b" }}>Aug 2026</span>
            </div>

            <div className="calendar-grid">
              <div className="calendar-day-header">S</div>
              <div className="calendar-day-header">M</div>
              <div className="calendar-day-header">T</div>
              <div className="calendar-day-header">W</div>
              <div className="calendar-day-header">T</div>
              <div className="calendar-day-header">F</div>
              <div className="calendar-day-header">S</div>

              <div className="calendar-day-cell">1</div>
              <div className="calendar-day-cell">2</div>
              <div className="calendar-day-cell">3</div>
              <div className="calendar-day-cell">4</div>
              <div className="calendar-day-cell">5</div>
              <div className="calendar-day-cell">6</div>
              <div className="calendar-day-cell">7</div>

              <div className="calendar-day-cell">8</div>
              <div className="calendar-day-cell">9</div>
              <div className="calendar-day-cell">10</div>
              <div className="calendar-day-cell">11</div>
              <div className="calendar-day-cell">12</div>
              <div className="calendar-day-cell">13</div>
              <div className="calendar-day-cell">14</div>

              <div className="calendar-day-cell">15</div>
              <div className="calendar-day-cell calendar-day-cell--active">16</div>
              <div className="calendar-day-cell">17</div>
              <div className="calendar-day-cell">18</div>
              <div className="calendar-day-cell">19</div>
              <div className="calendar-day-cell">20</div>
              <div className="calendar-day-cell">21</div>

              <div className="calendar-day-cell">22</div>
              <div className="calendar-day-cell">23</div>
              <div className="calendar-day-cell">24</div>
              <div className="calendar-day-cell">25</div>
              <div className="calendar-day-cell">26</div>
              <div className="calendar-day-cell">27</div>
              <div className="calendar-day-cell calendar-day-cell--highlight">28</div>
            </div>
          </div>

          {/* O-1 Readiness Activity Ring Widget */}
          <div className="dashboard-widget-card">
            <div className="widget-title">
              <span>O-1A Petition Readiness</span>
            </div>

            <div className="readiness-ring-container">
              <div className="readiness-circle-wrap">
                <div className="readiness-circle-inner">38%</div>
              </div>

              <div className="readiness-legend">
                <div className="readiness-legend-item">
                  <div className="readiness-dot" style={{ background: "#1e50e6" }} />
                  <span>3 Supported Criteria</span>
                </div>
                <div className="readiness-legend-item">
                  <div className="readiness-dot" style={{ background: "#f59e0b" }} />
                  <span>2 Partial Criteria</span>
                </div>
                <div className="readiness-legend-item">
                  <div className="readiness-dot" style={{ background: "#cbd5e1" }} />
                  <span>3 Gap Criteria</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
