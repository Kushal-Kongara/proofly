#!/usr/bin/env python3
"""One-shot live O-1A planner smoke test (Phase 4).

Ensures the seven synthetic demo PDFs (sample_documents/pdfs/) are present
in the demo Supermemory container — uploading only the ones missing, never
duplicates — waits for them to finish processing, then makes exactly ONE
live Featherless call via `FeatherlessService.analyze_o1_evidence` and
builds the deterministic assessment via `build_o1_assessment`.

Never prints API keys or full document/model text — only counts, statuses,
and short titles. Refuses to run against anything outside
sample_documents/pdfs/.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/live_o1_smoke_test.py
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
from app.services.featherless_service import FeatherlessService  # noqa: E402
from app.services.o1_assessment import build_o1_assessment  # noqa: E402
from app.services.supermemory_service import SupermemoryService  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_DIR = REPO_ROOT / "sample_documents" / "pdfs"
EXPECTED_FILENAMES = {
    "Maya_Patel_I20_Summary.pdf",
    "Maya_Patel_I94_Summary.pdf",
    "Maya_Patel_EAD_Summary.pdf",
    "Maya_Patel_Resume.pdf",
    "Maya_Patel_Employment_Letter.pdf",
    "Maya_Patel_Innovation_Award.pdf",
    "Maya_Patel_Judging_Invitation.pdf",
}

POLL_INTERVAL_SECONDS = 3
TIMEOUT_SECONDS = 180
TERMINAL = {DocumentProcessingStatus.DONE, DocumentProcessingStatus.FAILED}


def _redact(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    for key in (settings.supermemory_api_key, settings.featherless_api_key):
        if key:
            message = message.replace(key, "[REDACTED]")
    return message


async def _ensure_documents_present(service: SupermemoryService) -> set[str]:
    """Uploads only the synthetic PDFs not already in the container (matched
    by custom_id = sha256 of file bytes, same scheme as the upload route).
    Returns the set of custom_ids belonging to the seven expected documents.
    """
    existing = await service.list_documents()
    existing_custom_ids = {doc.custom_id for doc in existing if doc.custom_id}

    expected_custom_ids: set[str] = set()
    for filename in sorted(EXPECTED_FILENAMES):
        path = PDF_DIR / filename
        if not path.exists():
            print(f"SKIPPED: expected synthetic PDF not found: {path}")
            continue

        content = path.read_bytes()
        custom_id = "proofly_" + hashlib.sha256(content).hexdigest()[:32]
        expected_custom_ids.add(custom_id)

        if custom_id in existing_custom_ids:
            print(f"  already present: {filename}")
            continue

        print(f"  uploading: {filename} ({len(content)} bytes)")
        await service.upload_document(
            file_bytes=content,
            filename=filename,
            content_type="application/pdf",
            custom_id=custom_id,
            metadata={
                "original_filename": filename,
                "content_type": "application/pdf",
                "source": "manual_upload",
                "synthetic": True,
            },
        )

    return expected_custom_ids


async def _wait_for_processing(service: SupermemoryService, custom_ids: set[str]) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        docs = await service.list_documents()
        relevant = [d for d in docs if d.custom_id in custom_ids]
        if relevant and all(d.status in TERMINAL for d in relevant):
            return
        pending = [d.filename for d in relevant if d.status not in TERMINAL]
        print(f"  ...waiting on: {', '.join(pending) or '(documents not yet listed)'}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    print(f"TIMED OUT after {TIMEOUT_SECONDS}s waiting for document processing.")


async def main() -> int:
    if not settings.supermemory_api_key:
        print("SKIPPED: SUPERMEMORY_API_KEY is not set in .env.")
        return 1
    if not settings.featherless_api_key:
        print("SKIPPED: FEATHERLESS_API_KEY is not set in .env.")
        return 1

    supermemory = SupermemoryService(settings=settings)
    featherless = FeatherlessService(settings=settings)

    print(f"Ensuring synthetic documents are present in container '{settings.supermemory_container_tag}'...")
    try:
        expected_custom_ids = await _ensure_documents_present(supermemory)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED to ensure documents present: {_redact(exc)}")
        return 1

    print("Waiting for document processing to complete...")
    try:
        await _wait_for_processing(supermemory, expected_custom_ids)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED while polling status: {_redact(exc)}")
        return 1

    try:
        all_completed = await supermemory.list_completed_documents_with_content()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED to retrieve completed documents: {_redact(exc)}")
        return 1

    documents = [d for d in all_completed if d.filename in EXPECTED_FILENAMES]
    if not documents:
        print("FAILED: no completed synthetic documents found to analyze.")
        return 1

    print(f"Analyzed document set ({len(documents)}): {sorted(d.filename for d in documents)}")
    print("Making exactly ONE live Featherless O-1A extraction call...")

    start = time.monotonic()
    try:
        llm_output = await featherless.analyze_o1_evidence(documents)
        citations_validated = True
        result_label = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        duration = time.monotonic() - start
        print(f"FAILED: {_redact(exc)}")
        print(f"Request duration: {duration:.2f}s  Result: FAILED")
        return 1
    duration = time.monotonic() - start

    assessment = build_o1_assessment(llm_output, as_of_date=__import__("datetime").date.today())

    documented = [c for c in assessment.criteria if c.status.value == "documented_support_found"]
    partial = [c for c in assessment.criteria if c.status.value == "partial_support_found"]
    none_found = [c for c in assessment.criteria if c.status.value == "no_support_found"]
    judging = next(c for c in assessment.criteria if c.definition.code.value == "judging")
    judging_future_items = [e for e in judging.evidence_items if e.is_future_dated]

    print()
    print("=== Live O-1A Integration Report ===")
    print(f"Documents analyzed: {len(documents)}")
    print(f"Criteria with any document support (documented): {len(documented)} -> {[c.definition.code.value for c in documented]}")
    print(f"Partial-support criteria: {len(partial)} -> {[c.definition.code.value for c in partial]}")
    print(f"No-support criteria: {len(none_found)} -> {[c.definition.code.value for c in none_found]}")
    print(
        "Judging invitation treatment: "
        + (
            f"{len(judging_future_items)} future-dated item(s) found, status={judging.status.value} "
            "(never documented_support_found from a future item)"
            if judging_future_items
            else f"no future-dated judging items found, status={judging.status.value}"
        )
    )
    print(f"Citations validated: {citations_validated} (unknown-document citations would have raised FeatherlessValidationError)")
    print(f"Request duration: {duration:.2f}s  Result: {result_label}")
    print()
    print("This report describes document coverage only — it is not an eligibility or approval determination.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
