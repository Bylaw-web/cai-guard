# CAI Guard — Launch Playbook

A concrete plan to get the repo in front of the right people and maximize stars/downloads. Based on
what actually drives open-source adoption (a strong README, a demo asset, and a well-run Show HN /
Reddit sequence — Hacker News reliably out-drives Product Hunt for developer tools).

## 0. Before you post anything (the fundamentals)

The README and one demo asset do 80% of the work. Make sure:

- [ ] **README** leads with a one-line value prop, a Highlights list, and a copy-paste quickstart. (Done.)
- [ ] **A 15–30s demo GIF/video** at the top of the README: add a doc → weaken a `MUST` in Word → CAI
      flags "control-weakened" → Restore. This single asset is the highest-leverage thing you can add.
      Record with ScreenToGif / OBS, keep it under ~5 MB, drop it at `docs/demo.gif`, and uncomment the
      line in the README.
- [ ] **Repo metadata**: a crisp GitHub "About" description + website field, and **topics** (see below).
- [ ] **A tagged release** `v0.1.0` with the Windows installer attached as a binary asset, so
      "Downloads" is meaningful and non-devs can grab an `.exe` without cloning.
- [ ] Green tests badge (CI is included at `.github/workflows/ci.yml`).
- [ ] LICENSE, SECURITY, CONTRIBUTING, CHANGELOG present. (Done.)

### Suggested GitHub topics (discoverability / search)

```
docx  word  document-management  change-tracking  contract-management  compliance
governance  local-first  privacy  redline  diff  merkle  python  msoffice  legaltech
version-control  document-integrity  no-cloud
```

## 1. Positioning (say this everywhere, consistently)

> **A local change-firewall for your Word documents.** Lock a baseline; every future edit — yours, a
> coworker's, or an AI's — is classified (cosmetic / structural / semantic / control-weakened) and
> held for your approval. 100% local, deterministic, MIT.

Lead with the *problem* ("a MUST quietly became a may"), not the tech. Avoid hype words.

## 2. Launch sequence (≈2 weeks)

**Week 1 — warm up (build credibility, gather feedback, not a hard sell):**

- Post progress/screenshots in niche communities where this is genuinely useful:
  `r/selfhosted`, `r/privacy`, `r/legaltech`, `r/msoffice`, `r/Python`, `r/opensource`.
  Frame as "I built a local tool that catches when a clause gets silently weakened — feedback?"
- Publish a short **dev.to / blog post**: "Why I built a deterministic change-firewall for Word docs."
  Explain the two-axis (fidelity vs meaning) idea — it's the memorable hook.
- Fix issues people raise. Early goodwill compounds.

**Launch day (aim Tue–Thu, 7–10 AM PT / 10 AM–1 PM ET):**

- **Show HN**: title = `Show HN: CAI Guard – a local change-firewall for your Word documents`.
  Immediately post a founder's comment: the problem, why deterministic (not AI), how it's local, and
  an honest "what it doesn't do yet." Then **stay in the thread all day** and answer every comment —
  treat criticism as free product research.
- Cross-post the same day to the subreddits above and dev.to. Link the HN thread.
- Optional: **Product Hunt** as your "official" day — good for a non-dev audience and backlinks, but
  expect HN to send more high-intent traffic.

**Week 2 — sustain:**

- Turn the best HN/Reddit questions into README FAQ entries and issues.
- Label 5–10 **good first issues** so drive-by contributors can help.
- Reply to every issue quickly for the first few weeks; responsiveness converts stars into contributors.

## 3. Content angles that tend to land

- "Track Changes shows edits. This *governs* them." (comparison hook)
- "A `MUST` became a `may` and nobody noticed — until now." (concrete fear)
- "Catch when your AI assistant silently rewrites a contract." (rides the AI wave)
- "Byte-exact rollback for Word docs, no git required." (utility hook)

## 4. Metrics to watch

- Stars in first 72h (HN spike), then weekly trend.
- Release download count (attach the installer to the release).
- Issues opened by non-authors (a real engagement signal).
- Referrers in GitHub Insights → double down on whatever channel converts.

## 5. Honesty guardrails

Don't overclaim. It's v0.1: say so. "Try it on copies first." Being straight about limitations is
what earns trust on HN specifically, and trust is what turns a spike into sustained adoption.
