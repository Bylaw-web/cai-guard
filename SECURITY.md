# Security

CAI Guard is **local-first**. It is designed so your documents never leave your computer.

## Data flow

- **Documents** are read from disk and copied byte-for-byte into a local vault. They are never uploaded.
- **Baselines, vaults, and settings** live only in your user profile (`%LOCALAPPDATA%\CAIGuard` on
  Windows, `~/.config/CAIGuard` elsewhere). Nothing is written next to your documents.
- **The change engine and integrity guard are fully offline** — no network calls, no telemetry.
- **The Word add-in service** binds to `127.0.0.1` only and rejects any request whose `Host` header
  is not loopback (a defense against DNS-rebinding). It exposes read-only status for the open document.
- **The optional AI assistant** is the *only* feature that makes a network request, and *only* if you
  explicitly set an API key and use it. When used, the text of the document's sections is sent to the
  provider you chose (Anthropic, OpenAI, or your local Ollama). If you never set a key, no document
  text ever leaves the machine. Your key is stored in plaintext in your local settings file — treat
  that file as a secret.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Email the maintainer (see the GitHub
profile) or use GitHub's private "Report a vulnerability" advisory feature. Include steps to
reproduce and the impact. You'll get an acknowledgement within a few days.

## Scope & disclaimer

CAI Guard is provided under the MIT License **with no warranty**. It is an early release: verify
critical documents independently and keep your own backups. The vault is a convenience, not a
substitute for version control or a backup system.
