#!/usr/bin/env python3
"""One-shot live Supermemory smoke test.

Uploads exactly one synthetic demo PDF
(sample_documents/pdfs/Maya_Patel_Resume.pdf) through the real
SupermemoryService and polls until it reaches a terminal status or a
bounded timeout elapses. Never prints SUPERMEMORY_API_KEY. Does not upload
any real document — refuses to run against anything outside
sample_documents/pdfs/.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/live_smoke_test.py

Exits non-zero (with a non-secret reason) if SUPERMEMORY_API_KEY isn't
configured, rather than faking success.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.schemas.vault_document import DocumentProcessingStatus  # noqa: E402
from app.services.supermemory_service import SupermemoryService  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_PDF = REPO_ROOT / "sample_documents" / "pdfs" / "Maya_Patel_Resume.pdf"

POLL_INTERVAL_SECONDS = 3
TIMEOUT_SECONDS = 90
TERMINAL = {DocumentProcessingStatus.DONE, DocumentProcessingStatus.FAILED}


def _redact(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    api_key = settings.supermemory_api_key
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


async def main() -> int:
    if not settings.supermemory_api_key:
        print("SKIPPED: SUPERMEMORY_API_KEY is not set in .env — cannot run the live smoke test.")
        return 1

    if not DEMO_PDF.exists():
        print(f"SKIPPED: synthetic demo PDF not found at {DEMO_PDF}. Run scripts/generate_synthetic_pdfs.py first.")
        return 1

    content = DEMO_PDF.read_bytes()
    custom_id = "proofly_smoketest_" + hashlib.sha256(content).hexdigest()[:24]

    service = SupermemoryService(settings=settings)

    print(f"Uploading {DEMO_PDF.name} ({len(content)} bytes) to container '{settings.supermemory_container_tag}'...")
    try:
        uploaded = await service.upload_document(
            file_bytes=content,
            filename=DEMO_PDF.name,
            content_type="application/pdf",
            custom_id=custom_id,
            metadata={
                "original_filename": DEMO_PDF.name,
                "content_type": "application/pdf",
                "source": "manual_upload",
                "synthetic": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface a sanitized failure reason, never raw secrets
        print(f"FAILED to upload: {_redact(exc)}")
        return 1

    print(f"Uploaded. Supermemory document ID: {uploaded.id}  initial status: {uploaded.status.value}")

    deadline = time.monotonic() + TIMEOUT_SECONDS
    status = uploaded.status
    while status not in TERMINAL and time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            current = await service.get_document_status(uploaded.id)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED while polling status: {_redact(exc)}")
            return 1
        status = current.status
        print(f"  ...status: {status.value}")

    if status not in TERMINAL:
        print(f"TIMED OUT after {TIMEOUT_SECONDS}s. Document ID: {uploaded.id}  last status: {status.value}")
        return 1

    print(f"DONE. Document ID: {uploaded.id}  final status: {status.value}")
    return 0 if status == DocumentProcessingStatus.DONE else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
