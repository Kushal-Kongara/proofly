# Proofly — Product Spec

Built for Open Atlas 2026.

## Target User

International students and early-career professionals in the U.S. managing
their own immigration paperwork — particularly F-1 students transitioning
through OPT/STEM OPT who are evaluating or pursuing an O-1A extraordinary
ability petition. They juggle multiple documents (I-20, I-94, EAD cards,
employment letters) and multiple deadlines, usually without an immigration
attorney on retainer.

## Problem

Immigration status tracking is scattered across PDFs, emails, and government
portals. People lose track of which document says what, when their status or
work authorization expires, and whether the evidence they're accumulating
(awards, publications, judging invitations, media coverage) actually adds up
to a credible O-1A case. Mistakes here are high-stakes and hard to reverse.

## Locked Features (this hackathon)

1. **Immigration document vault** — a single place to store and browse the
   documents that define a user's status (I-20, I-94, EAD, offer/employment
   letters, awards, etc.).
2. **Visa/status compliance timeline** — a chronological view of status
   periods, employment authorization periods, and travel-document
   expirations derived from the vault. These are tracked as distinct
   concepts (see `docs/ARCHITECTURE.md`): immigration classification (e.g.
   F-1, often open-ended/"D/S"), employment authorization (OPT/STEM OPT,
   fixed EAD dates), and days until the visa stamp expires (a valid visa
   permits the holder to request admission at a U.S. port of entry; it
   does not guarantee admission or determine authorized stay) are never
   collapsed into one expiration date.
3. **Document-grounded chatbot** — answers questions using only the user's
   own uploaded documents (plus, later, official public sources), always
   citing what it drew from.
4. **O-1A evidence-readiness planner** — maps the user's documents/evidence
   against the eight regulatory O-1A criteria and shows where they stand.

## Non-Goals (explicitly out of scope)

- Filing or submitting anything to USCIS or any government agency.
- Acting as, or replacing, an immigration attorney.
- Real user accounts, authentication, or multi-tenant data isolation.
- Real document upload/OCR/RAG pipelines, chatbot inference, or Tavily web
  search — **Phase 1 ships data contracts and scaffolding only.**
- Support for visa categories beyond F-1/OPT/STEM OPT/O-1A in this build.
- Production-grade security, persistence, or scalability.

## Synthetic-Data-Only Demo Rule

This build uses **only fictional, synthetic demo data** (see
`sample_documents/demo_profile.json`). No real person's identity, documents,
or immigration history are used at any point. All names, SEVIS IDs, dates,
employers, and institutions in the demo are invented and internally
consistent for demo purposes only.

## Legal Disclaimer

Proofly provides **informational support only**. It does not provide legal
advice, does not create an attorney-client relationship, and must not be
relied upon as a substitute for consultation with a licensed immigration
attorney. All AI-derived facts are estimates that require user verification
against source documents.
