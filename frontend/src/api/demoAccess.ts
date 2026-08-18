/**
 * Pure derivation of the document vault's demo write-access rules (Phase
 * 7D), split out of client.ts so it's testable without import.meta.env.
 * Mirrors the backend's _reject_upload_if_blocked / _reject_if_demo_read_only
 * split in app/routers/documents.py.
 */

export function isUploadBlocked(demoReadOnly: boolean, demoAllowUploads: boolean): boolean {
  return demoReadOnly && !demoAllowUploads;
}

export function isDeleteBlocked(demoReadOnly: boolean): boolean {
  return demoReadOnly;
}
