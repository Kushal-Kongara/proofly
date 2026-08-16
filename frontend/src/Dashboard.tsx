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
  f1: "F-1",
  h1b: "H-1B",
  o1a: "O-1A",
  other: "Other",
};

const AUTH_TYPE_LABELS: Record<EmploymentAuthorizationRecord["authorization_type"], string> = {
  post_completion_opt: "Post-completion OPT",
  stem_opt_extension: "STEM OPT extension",
  other: "Employment authorization",
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
  if (days === null) return "No countdown (D/S)";
  if (status === "historical") return `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  if (days < 0) return `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}`;
  if (days === 0) return "Due today";
  return `${days} day${days === 1 ? "" : "s"} remaining`;
}

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

function NeedsReviewBadge() {
  return <span className="needs-review-badge">Needs review</span>;
}

export default function Dashboard() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [documents, setDocuments] = useState<VaultDocument[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [latest, docs] = await Promise.all([getLatestAnalysis(), listDocuments()]);
      setAnalysis(latest);
      setDocuments(docs);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Could not load the dashboard.");
    } finally {
      setLoadingInitial(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const completedDocumentCount = documents.filter((doc) => doc.status === "done").length;

  const handleAnalyze = async () => {
    setErrorMessage(null);
    setAnalyzing(true);
    try {
      const result = await runAnalysis();
      setAnalysis(result);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const filenameFor = (documentId: string): string => {
    const match = analysis?.analyzed_documents.find((doc) => doc.document_id === documentId);
    return match?.filename ?? documentId;
  };

  const currentAuth = analysis ? findCurrentAuthorization(analysis.employment_authorizations, analysis.as_of_date) : null;

  return (
    <section className="dashboard">
      <div className="dashboard-header">
        <h2>Dashboard</h2>
        <button className="analyze-btn" onClick={handleAnalyze} disabled={analyzing || completedDocumentCount === 0} type="button">
          {analyzing ? "Analyzing…" : "Analyze documents"}
        </button>
      </div>

      {completedDocumentCount === 0 && !loadingInitial && (
        <p className="dashboard-hint">Upload documents and wait for them to reach "Ready" before analyzing.</p>
      )}

      {analyzing && <p className="dashboard-status dashboard-status--loading">Analyzing documents with Featherless…</p>}
      {errorMessage && <p className="dashboard-status dashboard-status--error">{errorMessage}</p>}

      {loadingInitial && <p className="dashboard-empty">Loading…</p>}

      {!loadingInitial && !analysis && !analyzing && (
        <p className="dashboard-empty">No analysis has run yet. Click "Analyze documents" once documents are ready.</p>
      )}

      {analysis && (
        <>
          <div className="summary-cards">
            <div className="summary-card">
              <span className="summary-card-label">Reported classification</span>
              <span className="summary-card-value">
                {analysis.reported_classification ? CLASSIFICATION_LABELS[analysis.reported_classification.classification] : "Not yet determined"}
              </span>
              {analysis.reported_classification && (
                <span className="summary-card-detail">
                  Admit until: {analysis.reported_classification.admit_until.raw_value}
                </span>
              )}
              {analysis.reported_classification && <NeedsReviewBadge />}
            </div>

            <div className="summary-card">
              <span className="summary-card-label">Current work authorization</span>
              <span className="summary-card-value">{currentAuth ? AUTH_TYPE_LABELS[currentAuth.authorization_type] : "None on file"}</span>
              {currentAuth && <NeedsReviewBadge />}
            </div>

            <div className="summary-card">
              <span className="summary-card-label">Work authorization expiration</span>
              <span className="summary-card-value">{currentAuth?.end_date ? formatDateOnly(currentAuth.end_date) : "—"}</span>
              {currentAuth?.end_date && <NeedsReviewBadge />}
            </div>

            <div className="summary-card">
              <span className="summary-card-label">Documents analyzed</span>
              <span className="summary-card-value">{analysis.analyzed_documents.length}</span>
            </div>
          </div>

          {(analysis.conflicts.length > 0 || analysis.missing_information.length > 0 || analysis.warnings.length > 0) && (
            <div className="dashboard-notices">
              {analysis.warnings.map((warning, i) => (
                <p key={`warning-${i}`} className="notice notice--warning">
                  {warning.message}
                </p>
              ))}
              {analysis.conflicts.map((conflict, i) => (
                <p key={`conflict-${i}`} className="notice notice--conflict">
                  Conflicting information: {conflict.description}
                </p>
              ))}
              {analysis.missing_information.map((item, i) => (
                <p key={`missing-${i}`} className="notice notice--missing">
                  Missing information: {item.description}
                </p>
              ))}
            </div>
          )}

          <div className="timeline-section">
            <h3>Timeline</h3>
            <p className="timeline-as-of">As of {formatDateOnly(analysis.as_of_date)}</p>
            {analysis.timeline.length === 0 && <p className="dashboard-empty">No dated events yet.</p>}
            <div className="timeline-list">
              {analysis.timeline.map((event: TimelineAnalysisEvent, i) => (
                <div className={`timeline-row timeline-row--${event.status}`} key={i}>
                  <div className="timeline-row-main">
                    <span className={`category-badge category-badge--${event.category}`}>{CATEGORY_LABELS[event.category]}</span>
                    <span className="timeline-title">{event.title}</span>
                    <NeedsReviewBadge />
                  </div>
                  <div className="timeline-row-detail">
                    <span>{event.event_date ? formatDateOnly(event.event_date) : "No fixed date"}</span>
                    <span className={`countdown countdown--${event.status}`}>
                      {daysRemainingLabel(event.days_remaining, event.status)}
                    </span>
                  </div>
                  <p className="timeline-explanation">{event.explanation}</p>
                  {event.status === "historical" && (
                    <p className="timeline-historical-note">
                      This is a prior document event, not a missed deadline.
                    </p>
                  )}
                  <span className="timeline-source">
                    Source: {filenameFor(event.source.document_id)}
                    {event.source.page_number ? `, page ${event.source.page_number}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <p className="legal-disclaimer">Proofly organizes document-derived information and is not legal advice.</p>
    </section>
  );
}
