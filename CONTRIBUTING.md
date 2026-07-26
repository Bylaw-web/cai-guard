# Contributing to CAI Guard

Thanks for being here! CAI Guard is a small, focused project and contributions are very welcome —
bug reports, docs, tests, recognizers for new file types, and UI polish especially.

## Ground rules

- **The evidence path stays deterministic.** The classifier and integrity guard must never depend on
  an AI model or a network call. AI may *propose* edits; it never *decides* anything. Keep it that way.
- **Never modify a user's document except through an approved edit.** Read-only + vault is the contract.
- Keep the core dependency-light (stdlib + `python-docx`). Heavier deps belong to the optional app layer.

## Dev setup

```bash
git clone https://github.com/<your-username>/cai-guard.git
cd cai-guard
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run the tests before you push:

```bash
python tests/test_engine.py
python tests/test_roundtrip.py
```

Both should print `all cases pass` / `OK`. The engine tests are the fast way to check you didn't
change classification behavior; the roundtrip test exercises enroll → edit → detect → reject.

## Pull requests

1. Open an issue first for anything non-trivial so we can agree on the approach.
2. One logical change per PR; include a test if you touch the engine, alignment, or integrity code.
3. Describe the user-visible effect and how you verified it.
4. Be kind in review. This is a friendly project.

## Good first issues

Look for the [`good first issue`](https://github.com/<your-username>/cai-guard/labels/good%20first%20issue)
label. Some starters:

- Add words to the default Semantic Library (e.g. more obligation or condition phrases).
- A `caiguard diff <doc>` CLI command that prints the current-vs-baseline text diff.
- macOS/Linux packaging for the tray app.
- A short screen-recording for the README.

By contributing you agree your work is licensed under the project's [MIT License](LICENSE).
