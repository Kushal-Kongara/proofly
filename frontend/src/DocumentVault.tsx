import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  ApiError,
  TERMINAL_STATUSES,
  VaultDocument,
  deleteDocument,
  getDocumentStatus,
  listDocuments,
  uploadDocument,
} from "./api/documents";
import "./DocumentVault.css";

const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const POLL_INTERVAL_MS = 4000;

const STATUS_LABELS: Record<VaultDocument["status"], string> = {
  queued: "Queued",
  extracting: "Extracting",
  chunking: "Chunking",
  embedding: "Embedding",
  done: "Ready",
  failed: "Failed",
  unknown: "Unknown",
};

function hasValidExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString();
}

export default function DocumentVault() {
  const [documents, setDocuments] = useState<VaultDocument[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const documentsRef = useRef<VaultDocument[]>([]);
  const pollingInFlight = useRef(false);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Could not load documents.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  // Single polling loop for the component's lifetime. Reads the latest
  // documents via a ref (no stale closures) and only fetches status for
  // documents not yet in a terminal state — so a document stops being
  // polled the moment it reaches done/failed, without tearing down and
  // recreating the interval, and a mutex flag guards against overlap.
  useEffect(() => {
    const interval = setInterval(async () => {
      if (pollingInFlight.current) return;

      const pending = documentsRef.current.filter((doc) => !TERMINAL_STATUSES.has(doc.status));
      if (pending.length === 0) return;

      pollingInFlight.current = true;
      try {
        const updates = await Promise.all(
          pending.map(async (doc) => {
            try {
              return await getDocumentStatus(doc.id);
            } catch {
              return null;
            }
          }),
        );
        setDocuments((prev) =>
          prev.map((doc) => updates.find((updated) => updated && updated.id === doc.id) ?? doc),
        );
      } finally {
        pollingInFlight.current = false;
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  const uploadFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) return;

    setErrorMessage(null);
    setSuccessMessage(null);

    const rejected: string[] = [];
    const accepted: File[] = [];
    for (const file of files) {
      if (!hasValidExtension(file.name)) {
        rejected.push(`${file.name}: unsupported file type`);
        continue;
      }
      if (file.size === 0) {
        rejected.push(`${file.name}: file is empty`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejected.push(`${file.name}: exceeds 10 MB limit`);
        continue;
      }
      accepted.push(file);
    }

    setUploadingCount(accepted.length);

    let successCount = 0;
    const failures: string[] = [...rejected];

    for (const file of accepted) {
      try {
        const doc = await uploadDocument(file);
        setDocuments((prev) => [doc, ...prev]);
        successCount += 1;
      } catch (err) {
        failures.push(`${file.name}: ${err instanceof ApiError ? err.message : "upload failed"}`);
      }
    }

    setUploadingCount(0);
    if (successCount > 0) {
      setSuccessMessage(`Uploaded ${successCount} document${successCount === 1 ? "" : "s"}.`);
    }
    if (failures.length > 0) {
      setErrorMessage(failures.join(" · "));
    }
  }, []);

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    uploadFiles(files);
    event.target.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    uploadFiles(files);
  };

  const handleDelete = async (doc: VaultDocument) => {
    // Belt-and-suspenders: the button is disabled while a document is still
    // processing, but status can flip between renders — refuse client-side
    // too rather than relying solely on the backend's 409.
    if (!TERMINAL_STATUSES.has(doc.status)) return;

    const confirmed = window.confirm(`Delete "${doc.filename}"? This cannot be undone.`);
    if (!confirmed) return;

    try {
      await deleteDocument(doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : `Could not delete ${doc.filename}.`);
    }
  };

  return (
    <section className="vault">
      <div className="vault-header">
        <h2>Document Vault</h2>
        <p className="vault-subtitle">Synthetic demo documents only. Nothing here is a real record.</p>
      </div>

      <div
        className={`vault-dropzone${isDragging ? " vault-dropzone--dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <p className="vault-dropzone-title">Drag and drop files here, or click to browse</p>
        <p className="vault-dropzone-hint">
          Accepted: PDF, PNG, JPG, JPEG · Max 10 MB per file · Multiple files allowed
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={handleFileInputChange}
          className="vault-file-input"
        />
      </div>

      {uploadingCount > 0 && <p className="vault-status vault-status--loading">Uploading {uploadingCount} file{uploadingCount === 1 ? "" : "s"}…</p>}
      {successMessage && <p className="vault-status vault-status--success">{successMessage}</p>}
      {errorMessage && <p className="vault-status vault-status--error">{errorMessage}</p>}

      <div className="vault-list">
        {loadingList && <p className="vault-empty">Loading documents…</p>}
        {!loadingList && documents.length === 0 && (
          <p className="vault-empty">No documents uploaded yet.</p>
        )}
        {documents.map((doc) => (
          <div className="vault-card" key={doc.id}>
            <div className="vault-card-main">
              <span className="vault-card-filename">{doc.filename}</span>
              <span className="vault-card-meta">
                {doc.content_type} · Uploaded {formatTimestamp(doc.created_at)}
              </span>
            </div>
            <div className="vault-card-badges">
              <span className="vault-badge vault-badge--synthetic">Synthetic demo</span>
              <span className={`vault-badge vault-badge--status vault-badge--${doc.status}`}>
                {STATUS_LABELS[doc.status]}
              </span>
            </div>
            <button
              className="vault-delete-btn"
              onClick={() => handleDelete(doc)}
              disabled={!TERMINAL_STATUSES.has(doc.status)}
              title={
                TERMINAL_STATUSES.has(doc.status)
                  ? undefined
                  : "Still processing — delete becomes available once it finishes."
              }
              type="button"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
