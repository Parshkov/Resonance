---
mission: R15A-OAUTH-CORE (#134) reviewed under R15B-OAUTH-REVIEW (#135)
base_mission_issue: 134
review_issue: 135
run: R15B-OAUTH-REVIEW
review_type: independent exact-head protocol/security review (canonical claim on #135; non-exclusive on #134)
contributor: Parshkov
agent_id: parshkov-anthropic-fable51-r15b-fmd3
agent_or_model: Anthropic Claude Fable 5.1 (claude-fable-5-1)
runtime: Claude Code on the web (managed Linux container), Python 3.11.15, stdlib urllib probe, SQLite/in-memory runtime only
date: 2026-09-04
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable (no blind group on R15A/R15B)
reviewed_pr: PENDING — no #134 SUBMIT head exists at the time of this draft
exact_head: PENDING
base_main: 2dc34e275248d36345c08a1f5d8fa0754a73d2ae
prior_review_read_before_this_review: >
  None exists yet. The 3005f8a probe on claude/resonance-p0-lanes-0yu8l2 written
  by the R15A implementer while they briefly held #135 was NOT read or reused;
  this review's oracle is its own probe (tests/e2e/r15b_oauth_probe.py).
conflict_of_interest: >
  Same human sponsor (repository owner) and same model family (Anthropic
  Claude Fable 5.1) as the R15A implementer parshkov-anthropic-fable51-r15a-3f39,
  in a different session, branch and agent_id. This identity wrote no
  src/remote/** code and will not patch the core; findings are reproduced
  black-box so a reader can re-run them without trusting the reviewer.
  dima2010-anthropic-fable5-7328 (different sponsor) announced a private
  shadow implementation as a second, independent oracle on #134.
notes: >
  Status: WAITING_ON #134. Sections marked PENDING are filled only from the
  exact SHA named in the #134 SUBMIT comment. Nothing below is a verdict
  until that happens. This document does not occupy, reopen, or release the
  #134 canonical slot and is review input, not maintainer REVIEW_STATUS.
---

# Scope

Independent exact-head review of the canonical R15A OAuth core (#134) for
hosted MCP clients, against the #135 required-check list and the #134
acceptance sequence 1–16. The canonical user goal under test: a person who
receives only `https://resonance-production-cfe3.up.railway.app/mcp` connects
through ordinary hosted-client authorization with no manual MCP key, bearer
token, capability URL, or custom header.

Owned surface of this review: `tests/e2e/r15b_oauth_probe.py` (black-box
probe), `tests/e2e/test_r15b_oauth_probe_harness.py` (discriminating-power
self-test), this document. Not touched: `src/remote/**`, production wiring
(#136), WebMCP UI, R17 packaging.

# Method

1. Fresh reads of #134/#135/#136/#137 for claim handshakes; CLAIM on #135 at
   2026-09-04T05:24:36Z verified as the only canonical claim after the
   05:21:27Z RELEASE.
2. Wrote an external-style probe that starts from a base URL only and drives
   the flow through RFC 9728 → RFC 8414 → (RFC 7591) → authorize/consent →
   token → MCP, then the negative battery. It never follows a redirect to the
   client callback, keeps a cookie jar across the consent round-trip, redacts
   every secret it sees, and scans negative-path responses for leaked secrets.
3. Validated the probe's discriminating power against a self-contained
   conformant test double with 13 injectable defects: conformant → 0 FAIL;
   each defect → its intended step turns FAIL (see harness self-test).
4. Baseline on `main` @ `2dc34e2` (`python3 -m src.remote.server`): FAIL at
   steps 1b/2 (401 without `resource_metadata`; no protected-resource
   metadata), confirming the probe detects the pre-R15A state.
5. Public production origin could not be reached from this sandbox (egress
   proxy returns 403 on CONNECT); production evidence is #136/#137 scope.
6. PENDING: fetch the #134 SUBMIT SHA, run the focused OAuth tests and the
   full suite at that head, run the probe against the head's standalone
   server, read the core for the checks that are not observable black-box.

# Required checks (#135) — status matrix

| # | Check | Probe step(s) | Result at exact head |
|---|-------|---------------|----------------------|
| 1 | `/mcp` protected-resource behaviour (401 for no/invalid bearer) | 1, 12 | PENDING |
| 2 | `WWW-Authenticate` challenge ↔ resource metadata linkage | 1b, 2 | PENDING |
| 3 | Protected-resource metadata correctness (resource = `{issuer}/mcp`, `authorization_servers`) | 2 | PENDING |
| 4 | Authorization-server metadata correctness (issuer, endpoints, S256, `code`, `none`) | 3, 3b, 3c | PENDING |
| 5 | Browser authorize flow renders explicit consent (no code before consent) | 4, 4b, 4c, 5 | PENDING |
| 6 | PKCE S256 enforcement (required; `plain` refused; wrong verifier refused) | E1, 8, 8b | PENDING |
| 7 | Exact `state` round-trip | 6 | PENDING |
| 8 | Strict redirect URI matching / no open redirect (validated before any redirect) | 10, 10b | PENDING |
| 9 | Client registration / `client_id` behaviour for hosted clients | 3d | PENDING |
| 10 | Resource/audience binding (`invalid_target` at authorize and token) | 11, 11b | PENDING |
| 11 | Access token maps to an existing Resonance (R12) identity | 8-10.whoami, 13c | PENDING |
| 12 | No caller-selected identity | E2 | PENDING |
| 13 | Code single-use + expiry | 9 (+ source read for expiry) | PENDING |
| 14 | Revocation takes effect immediately (access + refresh) | 12, 12a, 12b | PENDING |
| 15 | Refresh / reconnect behaviour if implemented | 13a, 13b, 13c | PENDING |
| 16 | No token leakage in logs/errors | E5 (+ source read of logging) | PENDING |
| 17 | Stale MCP session recovery (unknown `Mcp-Session-Id` → 404) | 13d | PENDING |
| 18 | Thought-sharing consent remains separate from OAuth consent | E6 (+ source read) | PENDING |

# Black-box sequence (#135) — executed evidence

PENDING. Will be the redacted JSON report of
`python3 -m tests.e2e.r15b_oauth_probe --base http://127.0.0.1:<port>` run
against the exact head's `python3 -m src.remote.server`, plus the exact
commands and the focused/full unittest results at that SHA.

# Findings

PENDING.

# Verdict

PENDING — one of ACCEPT (with independently executed evidence) or
REQUEST_CHANGES (with exact reproduction and the smallest required fix),
posted to #135 with the reviewed SHA.

# Open questions for #134 (to be raised as HANDOFF/BLOCKED if material)

- Hosted-client redirect URIs: does the core accept RFC 7591 registration of
  arbitrary `https` redirect URIs (Claude/ChatGPT connector callbacks), or
  does it allowlist? The probe defaults to registration and falls back to
  `--client-id` / `--redirect-uri`.
- Refresh grants across restart: contract-level question owned by #136; the
  review only checks semantics within one process.
