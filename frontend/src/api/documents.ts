import { ApiError, apiFetch } from "./client";

export { ApiError };

export type DocumentProcessingStatus =
  | "queued"
  | "extracting"
  | "chunking"
  | "embedding"
  | "done"
  | "failed"
  | "unknown";

export interface VaultDocument {
  id: string;
  custom_id: string | null;
  filename: string;
  content_type: string;
  status: DocumentProcessingStatus;
  created_at: string | null;
  metadata: Record<string, string | number | boolean>;
  error: string | null;
}

export const TERMINAL_STATUSES: ReadonlySet<DocumentProcessingStatus> = new Set(["done", "failed"]);

export async function uploadDocument(file: File): Promise<VaultDocument> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch("/api/documents/upload", {
    method: "POST",
    body: formData,
  });

  return response.json();
}

export async function listDocuments(): Promise<VaultDocument[]> {
  const response = await apiFetch("/api/documents");
  return response.json();
}

export async function getDocumentStatus(documentId: string): Promise<VaultDocument> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/status`);
  return response.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiFetch(`/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}
