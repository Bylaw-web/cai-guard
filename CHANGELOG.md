# Changelog

All notable changes to CAI Guard are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [0.1.0] — 2026-07-25

First public release.

### Added
- Deterministic change engine: content + semantic hashing, content-based section alignment, and
  classification into cosmetic / structural / semantic / control-weakened, with per-token diffs.
- Data-driven **Semantic Library** (obligations, negation, frequency/scope, conditions/exceptions,
  stance verbs, party roles) and a user-defined **Lexicon** — all editable in Settings.
- **Integrity guard**: OOXML parts + relationships walked into a compositional Merkle rollup;
  named alerts for dropped parts, broken relationships, unreadable/zero-byte parts, and gutted files.
- **Dependency Graph** tab visualizing a document's internal structure and status.
- Byte-exact **vault** + one-click **Restore to locked**; atomic manifest and document writes.
- **Bulk operations**: lock an entire folder; **push-all** pending changes across every document (app + `caiguard push-all` CLI).
- Optional **AI assistant** (Anthropic / OpenAI / Ollama) that chats and proposes hash-bound edits; deterministic offline fallback with no key.
- **Word add-in** task pane showing live status for the open document, backed by a loopback-only service.
- Windows installer (`install.ps1`) and PyInstaller/Inno packaging.

### Notes
- Baselines and vaults are stored in the OS app-data folder, never next to your documents.
- The engine and integrity guard are fully offline; only the optional AI assistant makes network calls.

[0.1.0]: https://github.com/<your-username>/cai-guard/releases/tag/v0.1.0
