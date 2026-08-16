import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  O1Assessment,
  O1CriterionAssessment,
  O1CriterionStatus,
  O1EvidenceItem,
  getLatestO1Assessment,
  runO1Assessment,
} from "./api/o1";
import { VaultDocument, listDocuments } from "./api/documents";
import { formatDateOnly } from "./lib/date";
import "./O1Plan.css";

const STATUS_LABELS: Record<O1CriterionStatus, string> = {
  documented_support_found: "Document support found",
  partial_support_found: "Partial documentation",
  no_support_found: "No supporting document found",
  needs_expert_review: "Needs expert review",
};

const COVERAGE_LABELS: Record<O1Assessment["summary"]["documentation_coverage"], string> = {
  limited: "Limited",
  developing: "Developing",
  broad: "Broad",
};

const ROLE_LABELS: Record<O1EvidenceItem["evidence_role"], string> = {
  direct_document: "Direct document evidence",
  supporting_document: "Supporting document",
  self_reported: "Self-reported (resume/CV)",
};

const PRIORITY_LABELS: Record<"high" | "medium" | "low", string> = {
  high: "High priority",
  medium: "Medium priority",
  low: "Low priority",
};

function EvidenceCard({ item }: { item: O1EvidenceItem }) {
  return (
    <div className={`o1-evidence-card${item.is_future_dated ? " o1-evidence-card--future" : ""}`}>
      <div className="o1-evidence-card-header">
        <span className="o1-evidence-title">{item.title}</span>
        <span className={`o1-role-badge o1-role-badge--${item.evidence_role}`}>{ROLE_LABELS[item.evidence_role]}</span>
        {item.is_future_dated && <span className="o1-future-badge">Planned / future evidence</span>}
      </div>
      <p className="o1-evidence-summary">{item.factual_summary}</p>
      {item.limitations.length > 0 && (
        <ul className="o1-evidence-limitations">
          {item.limitations.map((limitation, i) => (
            <li key={i}>{limitation}</li>
          ))}
        </ul>
      )}
      <div className="o1-evidence-meta">
        <span>Source: {item.source_filename}{item.page_number ? `, page ${item.page_number}` : ""}</span>
        {item.date && <span>Document date: {formatDateOnly(item.date)}</span>}
        <span className="o1-needs-review-badge">Needs review</span>
      </div>
    </div>
  );
}

function CriterionCard({ assessment }: { assessment: O1CriterionAssessment }) {
  const { definition, status, evidence_items, why_documents_may_be_relevant, what_remains_unproven, suggested_evidence_to_collect } = assessment;
  const futureItems = evidence_items.filter((item) => item.is_future_dated);
  const documentedItems = evidence_items.filter((item) => !item.is_future_dated);

  return (
    <div className={`o1-criterion-card o1-criterion-card--${status}`}>
      <div className="o1-criterion-header">
        <h3>{definition.name}</h3>
        <span className={`o1-status-badge o1-status-badge--${status}`}>{STATUS_LABELS[status]}</span>
      </div>
      <p className="o1-criterion-description">{definition.regulatory_description}</p>

      <p className="o1-criterion-why">{why_documents_may_be_relevant}</p>

      {documentedItems.length > 0 && (
        <div className="o1-evidence-group">
          <span className="o1-evidence-group-label">Documented evidence</span>
          {documentedItems.map((item) => (
            <EvidenceCard item={item} key={item.id} />
          ))}
        </div>
      )}

      {futureItems.length > 0 && (
        <div className="o1-evidence-group">
          <span className="o1-evidence-group-label">Planned / future evidence</span>
          {futureItems.map((item) => (
            <EvidenceCard item={item} key={item.id} />
          ))}
        </div>
      )}

      <div className="o1-criterion-gap">
        <span className="o1-criterion-gap-label">What remains unproven</span>
        <p>{what_remains_unproven}</p>
      </div>

      {suggested_evidence_to_collect.length > 0 && (
        <div className="o1-criterion-suggested">
          <span className="o1-criterion-gap-label">Suggested evidence to collect</span>
          <ul>
            {suggested_evidence_to_collect.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="o1-attorney-note">Requires attorney review before any conclusion is drawn.</p>
    </div>
  );
}

export default function O1Plan() {
  const [assessment, setAssessment] = useState<O1Assessment | null>(null);
  const [documents, setDocuments] = useState<VaultDocument[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [running, setRunning] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [latest, docs] = await Promise.all([getLatestO1Assessment(), listDocuments()]);
      setAssessment(latest);
      setDocuments(docs);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Could not load the O-1 evidence plan.");
    } finally {
      setLoadingInitial(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const completedDocumentCount = documents.filter((doc) => doc.status === "done").length;

  const handleRun = async () => {
    setErrorMessage(null);
    setRunning(true);
    try {
      const result = await runO1Assessment();
      setAssessment(result);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Building the evidence plan failed.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="o1-plan">
      <div className="o1-plan-header">
        <div>
          <h2>O-1 Evidence Readiness</h2>
          <p className="o1-plan-subtitle">Organizes your documents against the eight O-1A criteria and identifies evidence gaps.</p>
        </div>
        <div className="o1-plan-header-actions">
          <button className="o1-build-btn" onClick={handleRun} disabled={running || completedDocumentCount === 0} type="button">
            {running ? "Building…" : "Build my evidence plan"}
          </button>
          {assessment && (
            <button className="o1-print-btn" onClick={() => window.print()} type="button">
              Print / Save report
            </button>
          )}
        </div>
      </div>

      {completedDocumentCount === 0 && !loadingInitial && (
        <p className="o1-plan-hint">Upload documents and wait for them to reach "Ready" before building an evidence plan.</p>
      )}

      {running && <p className="o1-plan-status o1-plan-status--loading">Analyzing documents with Featherless…</p>}
      {errorMessage && <p className="o1-plan-status o1-plan-status--error">{errorMessage}</p>}
      {loadingInitial && <p className="o1-plan-empty">Loading…</p>}

      {!loadingInitial && !assessment && !running && (
        <p className="o1-plan-empty">No evidence plan has been built yet. Click "Build my evidence plan" once documents are ready.</p>
      )}

      {assessment && (
        <>
          <div className="o1-coverage-summary">
            <div className="o1-coverage-cards">
              <div className="o1-coverage-card">
                <span className="o1-coverage-card-label">Documentation coverage</span>
                <span className="o1-coverage-card-value">{COVERAGE_LABELS[assessment.summary.documentation_coverage]}</span>
              </div>
              <div className="o1-coverage-card">
                <span className="o1-coverage-card-label">Document support found</span>
                <span className="o1-coverage-card-value">{assessment.summary.criteria_with_document_support_count} / 8</span>
              </div>
              <div className="o1-coverage-card">
                <span className="o1-coverage-card-label">Partial documentation</span>
                <span className="o1-coverage-card-value">{assessment.summary.criteria_with_partial_support_count} / 8</span>
              </div>
              <div className="o1-coverage-card">
                <span className="o1-coverage-card-label">No supporting document</span>
                <span className="o1-coverage-card-value">{assessment.summary.criteria_without_support_count} / 8</span>
              </div>
              {assessment.summary.criteria_needing_expert_review_count > 0 && (
                <div className="o1-coverage-card">
                  <span className="o1-coverage-card-label">Needs expert review</span>
                  <span className="o1-coverage-card-value">{assessment.summary.criteria_needing_expert_review_count} / 8</span>
                </div>
              )}
            </div>

            <p className="o1-coverage-disclaimer">{assessment.summary.disclaimer}</p>

            <div className="o1-informational-flags">
              <span className={`o1-flag-badge${assessment.summary.one_time_achievement_documented ? " o1-flag-badge--present" : ""}`}>
                One-time major achievement: {assessment.summary.one_time_achievement_documented ? "documented" : "not documented"}
              </span>
              <span className={`o1-flag-badge${assessment.summary.comparable_evidence_identified ? " o1-flag-badge--present" : ""}`}>
                Comparable evidence: {assessment.summary.comparable_evidence_identified ? "identified" : "not identified"}
              </span>
            </div>

            <p className="o1-plan-as-of">As of {formatDateOnly(assessment.as_of_date)}</p>
          </div>

          {assessment.summary.highest_priority_gaps.length > 0 && (
            <div className="o1-gaps-section">
              <h3>Highest-priority gaps</h3>
              <ul className="o1-gaps-list">
                {assessment.summary.highest_priority_gaps.map((gap, i) => (
                  <li key={i} className={`o1-gap-row o1-gap-row--${gap.priority}`}>
                    <span className="o1-gap-priority">{PRIORITY_LABELS[gap.priority]}</span>
                    <span>{gap.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="o1-criteria-section">
            <h3>Criteria</h3>
            <div className="o1-criteria-grid">
              {assessment.criteria.map((c) => (
                <CriterionCard assessment={c} key={c.definition.code} />
              ))}
            </div>
          </div>

          <div className="o1-action-plan-section">
            <h3>Evidence-gathering action plan</h3>
            <div className="o1-action-list">
              {assessment.action_plan.map((action, i) => (
                <div key={i} className={`o1-action-row o1-action-row--${action.priority}`}>
                  <div className="o1-action-row-header">
                    <span className={`o1-priority-badge o1-priority-badge--${action.priority}`}>{PRIORITY_LABELS[action.priority]}</span>
                    <span className="o1-action-type">{action.action_type.replace(/_/g, " ")}</span>
                  </div>
                  <p className="o1-action-text">{action.action}</p>
                  <p className="o1-action-why">{action.why_it_matters}</p>
                  {action.suggested_supporting_materials.length > 0 && (
                    <ul className="o1-action-materials">
                      {action.suggested_supporting_materials.map((m, j) => (
                        <li key={j}>{m}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="o1-sources-section">
            <span className="o1-criterion-gap-label">Official sources</span>
            <ul>
              {assessment.summary.official_sources.map((url, i) => (
                <li key={i}>
                  <a href={url} target="_blank" rel="noreferrer">
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      <p className="legal-disclaimer">
        Proofly evaluates document readiness, not visa eligibility. An attorney must evaluate the complete case.
      </p>
    </section>
  );
}
