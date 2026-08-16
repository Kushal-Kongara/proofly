import { ApiError, apiFetch } from "./client";

export { ApiError };

export type ImmigrationClassification = "f1" | "h1b" | "o1a" | "other";
export type EmploymentAuthorizationType = "post_completion_opt" | "stem_opt_extension" | "other";
export type AnalyzedDocumentType =
  | "i20"
  | "i94"
  | "ead"
  | "f1_approval"
  | "visa_stamp"
  | "resume"
  | "employment_letter"
  | "award"
  | "judging_invitation"
  | "other";
export type AdmitUntilType = "duration_of_status" | "fixed_date" | "unknown";

export interface SourceCitation {
  document_id: string;
  page_number: number | null;
  excerpt: string | null;
}

export interface AnalysisFact {
  label: string;
  value: string;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface AnalyzedDocument {
  document_id: string;
  filename: string;
  document_type: AnalyzedDocumentType;
  facts: AnalysisFact[];
}

export interface I94AdmitUntil {
  type: AdmitUntilType;
  raw_value: string;
  admit_until_date: string | null;
}

export interface ReportedImmigrationClassification {
  classification: ImmigrationClassification;
  admit_until: I94AdmitUntil;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface AcademicProgramRecord {
  school_name: string | null;
  program_name: string | null;
  program_start_date: string | null;
  program_end_date: string | null;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface EmploymentAuthorizationRecord {
  authorization_type: EmploymentAuthorizationType;
  start_date: string | null;
  end_date: string | null;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface VisaStampRecord {
  visa_class: string | null;
  issue_date: string | null;
  expiration_date: string | null;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface PassportRecord {
  expiration_date: string;
  source_document_id: string;
  source_filename: string;
  page_number: number | null;
  confidence: number;
  verification_status: "needs_user_review";
}

export interface AnalysisConflict {
  description: string;
  involved_document_ids: string[];
}

export interface MissingInformationItem {
  description: string;
  related_document_id: string | null;
}

export interface AnalysisWarning {
  message: string;
}

export type TimelineEventCategory =
  | "work_authorization"
  | "visa_validity"
  | "academic_program"
  | "passport"
  | "status"
  | "other";
export type TimelineEventDisplayStatus = "upcoming" | "urgent" | "overdue" | "historical" | "informational";

export interface TimelineAnalysisEvent {
  title: string;
  event_date: string | null;
  category: TimelineEventCategory;
  days_remaining: number | null;
  status: TimelineEventDisplayStatus;
  source: SourceCitation;
  explanation: string;
  affects_authorized_stay: boolean | null;
  requires_user_verification: boolean;
}

export interface AnalysisResult {
  analyzed_documents: AnalyzedDocument[];
  reported_classification: ReportedImmigrationClassification | null;
  academic_program: AcademicProgramRecord | null;
  employment_authorizations: EmploymentAuthorizationRecord[];
  visa_stamps: VisaStampRecord[];
  passport: PassportRecord | null;
  conflicts: AnalysisConflict[];
  missing_information: MissingInformationItem[];
  warnings: AnalysisWarning[];
  as_of_date: string;
  timeline: TimelineAnalysisEvent[];
}

export async function runAnalysis(): Promise<AnalysisResult> {
  const response = await apiFetch("/api/analysis/run", { method: "POST" });
  return response.json();
}

export async function getLatestAnalysis(): Promise<AnalysisResult | null> {
  try {
    const response = await apiFetch("/api/analysis/latest");
    return await response.json();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
