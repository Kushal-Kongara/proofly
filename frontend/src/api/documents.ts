const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON — fall through to a generic message
  }
  return `Request failed with status ${response.status}`;
}

export async function uploadDocument(file: File): Promise<VaultDocument> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }

  return response.json();
}

export async function listDocuments(): Promise<VaultDocument[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function getDocumentStatus(documentId: string): Promise<VaultDocument> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/status`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
}
