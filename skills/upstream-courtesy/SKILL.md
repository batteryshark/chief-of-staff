---
name: upstream-courtesy
description: Use when preparing or sending an upstream issue, bug report, comment, patch, PR or follow-up to someone else's project; not internal bug fixes. Prepare a concise private draft with real proof; ask the principal/user before posting.
---
<!-- managed by chief-of-staff/install.sh; upstream-courtesy -->

# Upstream courtesy

Assume a human maintainer reads every submission. Their time is scarce: send
useful, legitimate, reproducible bugs, not AI-generated noise or floods.
These rules apply to reports, issues, comments, patches, PRs and follow-ups.

## Local modifications and licensing

- Fork only if we modify upstream code: keep attribution and reference the fork
  over maintainer outreach for local modifications. Unmodified upstream code is
  referenced or included/vendored with its notices, whichever fits the project.
  A missing upstream LICENSE alone is no reason to block, ask, file an issue or
  escalate; handle an objection if raised. This operating policy does not assert
  a permission grant from a public repo or missing file.
- Use our own licence for our own work in our repositories, not to relicense copied
  third-party code. Keep bundled dependencies' shipped notices, attribution and
  explicit existing terms; never strip or invent licence text. Skip exhaustive
  licence chaining or provenance audits unless an obvious real legal risk needs
  attention; a missing file alone is not that exception.
- Actual forks, pushes and other outward steps still follow the approved plan and
  reserved approvals. Real bug reports, patches and submissions still follow the
  courtesy and principal-approval rules below; no automatic contact or floods.

## 1. Triage before drafting

- Establish a real, plausibly generalizable bug on a supported/documented path.
  Reproduce in a clean environment on the current supported version. Separate
  upstream behavior from our misuse, configuration, custom wrapper or fork.
  An own-environment failure can still be general if others plausibly use that
  documented path; do not invent user counts or demand absolute certainty.
- If uncertain, keep investigating privately; do not accuse upstream. Ask whether
  a fix benefits users and is proportionate, narrow and low-risk. For patches,
  test the failure, fix and compatibility; do not present broad cleanup, rewrites
  or unsupported feature requests as bug fixes.
- Serious risks or sensitive vulnerabilities need the project's security channel
  and principal approval. Never publish an exploit dump.

## 2. Respect the project's rules

- Before drafting, read CONTRIBUTING, issue/PR templates, support scope, security
  guidance and AI-use policy; search docs and open AND closed issues/PRs for duplicates.
  Unknown/unavailable policy stays unknown: defer posting. Confirmed
  absence of a published AI policy is not refusal; follow known contribution rules.
- Use an existing thread only for material new evidence and with approval, not
  duplicate reports or pile-ons. If AI disclosure is required, disclose honestly.
  If AI assistance is refused, STOP: no rewording, laundering or human proxy to
  evade that refusal, even with principal approval. Concise prose is not hiding AI use or
  impersonating a human. Never claim manual work that was not done.

## 3. Build small, real proof

- Keep a full private evidence journal. Extract a tiny self-contained reproduction
  on the supported path: exact version, platform, necessary configuration, steps
  or snippet, expected versus actual behavior and real observed failure. Include
  a control, fix or regression test where applicable; state what was not tested.
- Never invent runs, screenshots, timings, performance claims or other evidence.
  Separate confirmed facts from hypotheses and any brief suggested fix.
- Redact credentials, private paths and user data. Share only necessary sanitized
  logs, not internal transcripts or the whole private journal.

## 4. Draft for the person reading it

- Use THEIR template, in short plain professional prose: version, minimal steps,
  expected/actual, practical impact and a brief suggestion only if helpful.
  No generic AI preamble, oversold root cause or essay.
- Omit internal agent jargon, lane/trace IDs, hashes and offsets unless genuinely
  necessary, requested by maintainers or required by their template. A version
  commit is a legitimate required hash; do not omit mandatory fields.
- One issue per distinct bug; keep separate private cases for unrelated bugs.
  Do not bundle unrelated fixes or automatically spray multiple posts.

## 5. Approval is separate from readiness

- Obtain the principal/user's explicit yes BEFORE ANY outward submission: issue,
  comment, PR, patch, review message, upload, edit or follow-up. Approval names the
  exact actions, destinations, content, revisions and channels; a finite enumerated
  set may be approved in advance. Changed/unlisted actions need a fresh yes, never
  assumed follow-up. Local skill creation/installation is not reporting permission.
- Workers send private drafts and evidence to their lead; the lead requests the
  principal's decision through the existing owner/chief route. Without that
  hierarchy, ask the principal/user directly. Preserve all reserved approvals.
- No default autoposting or publishing command. A tool/skill that auto-publishes
  (including a report skill) does NOT override this gate: courtesy comes first.
  Missing approval or unavailable safe channels means keep the draft private.

## 6. Follow up without adding noise

- Send only polite, concise, material new tested information or answers, with
  exact advance approval or a fresh yes. Respect decisions; no repeated pings, duplicate
  cross-posts, bot spam or unrequested patch floods. If rejected, accept it or
  clarify once if asked; never evade a refusal.
- Track one outstanding thread per case and its allowed next contact privately.
  Do not schedule automatic outreach.

## Private handoff (not an upstream form)
Record: triage verdict and uncertainty; policy/duplicate findings; minimal repro
and observed evidence; short draft in the target template; exact proposed
destination/channel/revision; approval status and allowed next contact.
If no template exists, use: **Version/environment → Steps → Expected → Actual →
Impact**, plus a brief evidence-backed suggestion if useful. Stop at a private
draft until the principal says yes.
