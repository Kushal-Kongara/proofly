import { ApiError, apiFetch } from "./client";

export { ApiError };

export type O1CriterionCode =
  | "awards"
  | "membership"
  | "published_material"
  | "judging"
  | "original_contribution"
  | "scholarly_articles"
  | "critical_employment"
  | "high_remuneration";

export type O1EvidenceRole = "direct_document" | "supporting_document" | "self_reported";

export type O1CriterionStatus =
  | "documented_support_found"
  | "partial_support_found"
  | "no_support_found"
  | "needs_expert_review";

export type O1DocumentationCoverage = "limited" | "developing" | "broad";

export type O1ActionType =
  | "collect_document"
  | "request_confirmation"
  | "collect_metrics"
  | "obtain_independent_evidence"
  | "verify_fact"
  | "attorney_review";

export type O1ActionPriority = "high" | "medium" | "low";

export interface O1CriterionDefinition {
  code: O1CriterionCode;
  name: string;
  regulatory_description: string;
  official_sources: string[];
}

export interface O1InformationalCategory {
  name: string;
  description: string;
  official_sources: string[];
}

export interface O1CriteriaResponse {
  criteria: O1CriterionDefinition[];
  one_time_achievement: O1InformationalCategory;
  comparable_evidence: O1InformationalCategory;
  official_sources: string[];
  last_reviewed: string;
}

export interface O1EvidenceItem {
  id: string;
  title: string;
  factual_summary: string;
  criterion_id: O1CriterionCode;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
  evidence_role: O1EvidenceRole;
  limitations: string[];
  date: string | null;
  is_future_dated: boolean;
  is_one_time_major_achievement: boolean;
  is_comparable_evidence: boolean;
}

export interface O1CriterionAssessment {
  definition: O1CriterionDefinition;
  status: O1CriterionStatus;
  evidence_items: O1EvidenceItem[];
  why_documents_may_be_relevant: string;
  what_remains_unproven: string;
  suggested_evidence_to_collect: string[];
  requires_attorney_review: true;
}

export interface O1Gap {
  criterion_id: O1CriterionCode;
  description: string;
  priority: O1ActionPriority;
}

export interface O1ActionItem {
  action_type: O1ActionType;
  priority: O1ActionPriority;
  related_criterion: O1CriterionCode | null;
  action: string;
  why_it_matters: string;
  suggested_supporting_materials: string[];
}

export interface O1AssessmentSummary {
  criteria_with_document_support_count: number;
  criteria_with_partial_support_count: number;
  criteria_without_support_count: number;
  criteria_needing_expert_review_count: number;
  one_time_achievement_documented: boolean;
  comparable_evidence_identified: boolean;
  documentation_coverage: O1DocumentationCoverage;
  highest_priority_gaps: O1Gap[];
  disclaimer: string;
  official_sources: string[];
}

export interface O1Assessment {
  criteria: O1CriterionAssessment[];
  summary: O1AssessmentSummary;
  action_plan: O1ActionItem[];
  as_of_date: string;
}

export async function getO1Criteria(): Promise<O1CriteriaResponse> {
  const response = await apiFetch("/api/o1/criteria");
  return response.json();
}

export async function runO1Assessment(): Promise<O1Assessment> {
  const response = await apiFetch("/api/o1/assessment/run", { method: "POST" });
  return response.json();
}

export async function getLatestO1Assessment(): Promise<O1Assessment | null> {
  try {
    const response = await apiFetch("/api/o1/assessment/latest");
    return await response.json();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
