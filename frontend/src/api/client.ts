import { isDeleteBlocked, isUploadBlocked } from "./demoAccess";
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";
import { resolveDemoAllowUploads } from "./resolveDemoAllowUploads";
import { resolveDemoReadOnly } from "./resolveDemoReadOnly";

export const API_BASE_URL = resolveApiBaseUrl(import.meta.env);
export const DEMO_READ_ONLY = resolveDemoReadOnly(import.meta.env);
export const DEMO_ALLOW_UPLOADS = resolveDemoAllowUploads(import.meta.env);

export const UPLOAD_BLOCKED = isUploadBlocked(DEMO_READ_ONLY, DEMO_ALLOW_UPLOADS);
export const DELETE_BLOCKED = isDeleteBlocked(DEMO_READ_ONLY);

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

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response;
}
