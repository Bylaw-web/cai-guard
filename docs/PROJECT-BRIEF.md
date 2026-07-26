# CAI Guard — Project Brief

## One line

Stop AI from silently breaking your documents: lock a baseline, and every edit an AI (or anyone)
makes is classified and held for your approval, with one-click rollback — catching weakened clauses,
dropped parts, and corrupted files before they ship.

## The problem

Documents that matter — contracts, policies, resumes, specs, SOWs — are edited by many hands and,
increasingly, by AI assistants. The dangerous changes are the quiet ones: an obligation softened
(`MUST → may`), a cap or date changed, a carve-out added ("except…"), a dropped comment, or a file
that silently becomes corrupt. "Track Changes" shows edits *while a person is watching*; it doesn't
classify them by severity, doesn't survive being turned off, and can't see structural corruption.
Version control (git) is for code and text, not `.docx`, and non-technical owners don't use it.

## The solution

CAI Guard takes a byte-exact baseline of a document and then, on every save, deterministically
classifies what changed — cosmetic, structural, semantic, or **control-weakened** — and holds it for
approve/reject. A separate integrity pass fingerprints the document's internal structure to catch
corruption text-diffing can't see. Everything runs locally; nothing is trusted to an AI or sent to a
server.

## Who it's for

- **Contract / legal ops** who need to know when an obligation or number changed.
- **Compliance / policy owners** governing controlled documents.
- **Job seekers & writers** with many near-duplicate documents (e.g. tailored resumes) who want to
  lock a known-good version.
- **Anyone using AI to edit documents** who wants a human checkpoint before changes land.

## What makes it different

- **Deterministic, not AI-judged.** The verdict is reproducible and explainable — it names the exact
  tokens that changed. AI is optional and only ever *proposes*.
- **Two independent axes.** Fidelity (bytes) and meaning (governance tokens) are tracked separately,
  so a formatting tweak and a weakened obligation are never confused.
- **Structure-aware.** It understands a `.docx` as a package of parts and relationships, so it catches
  corruption and dropped parts, not just text changes.
- **Local-first.** No cloud, no account, no telemetry.

## Positioning statement

> **CAI Guard is version-lock and change-governance for the documents you edit in Word — like a
> firewall for your files.** Track Changes shows edits; CAI Guard decides whether they're allowed to
> stay, and can roll any document back to a byte-exact baseline in one click.

## Status

v0.1, MIT-licensed, actively developed. Core lock/classify/restore path is test-covered and has been
run across hundreds of documents.
