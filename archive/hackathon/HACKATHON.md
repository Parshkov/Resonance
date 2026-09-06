# Resonance — WebMCP Challenge build record

This document separates the pre-existing Resonance concept and accepted engine from work added during the WebMCP Challenge submission period.

## Before the hackathon submission work

Resonance already had the central product/research direction: represent thought as structured Thought DNA / Thought Graph artifacts, retrieve candidates cheaply, and verify structural resonance with explicit evidence rather than asking an LLM for an opaque compatibility score. The repository also already contained the accepted structural engine chain, deterministic benchmark/fixture work, a classic stdio MCP adapter, and the R8 discovery contract.

Those components are not described as WebMCP.

## Hackathon-period browser work

The competition build adds the browser-facing product and WebMCP path on top of the accepted engine contracts:

- R9 visual discovery client for a recordable one-screen map/match/evidence experience;
- R10 browser WebMCP registration through `document.modelContext.registerTool(...)`;
- safe private prepare -> read-only preview -> explicit share confirmation semantics;
- opaque preview confirmation tokens so the state-changing share call cannot skip the preview step;
- retry-safe state-changing tools with stable caller-supplied `request_id` keys, duplicate-write replay, idempotency-key conflict detection, committed-operation reconciliation after cancellation/response loss, and authoritative state refresh;
- browser discovery responses receive bounded opaque `result_id` records, and match-evidence reads require that id so LIVE discovery cannot silently fall back to REPLAY state;
- browser consent revocation clears retained discovery results and fails later discovery/evidence reads closed;
- same-origin write enforcement, browser security headers, static schemas/tool descriptions, read-only and untrusted-content annotations, registration ownership via `AbortController`, and execution `AbortSignal` propagation;
- Apache-2.0 repository license selected explicitly by the owner for the public submission and detected by GitHub repository metadata.

Parallel product missions add durable persistence, identity/consent, live multi-user behavior, collaboration, deployment, and final submission packaging. Their issue/PR provenance remains separate rather than being retroactively attributed to R10.

## WebMCP is not classic MCP

Resonance supports more than one transport. The accepted classic MCP path is a newline-delimited stdio server used by the engine/demo integration. The WebMCP Challenge path is different: a browser page exposes progressive-enhancement tools through `document.modelContext.registerTool(...)` and invokes the same product/backend semantics from the page.

R10 therefore does not rename stdio MCP as WebMCP, and it does not put matching logic into browser JavaScript.

## R10 browser tool surface

- `resonance_prepare_thought`
- `resonance_get_share_preview`
- `resonance_share_prepared_thought`
- `resonance_discover`
- `resonance_get_match`
- `resonance_update_consent`

The preparation tool creates a private draft only. The preview is read-only and returns the opaque token required by the share tool. Sharing requires both an explicit confirmation input and that preview token. Revocation immediately blocks browser discovery; restoring sharing intentionally requires a new prepare -> preview -> share flow instead of `resonance_update_consent(shared=true)`.

`resonance_discover` returns a `result_id` that names the exact accepted payload/source retained by R10. `resonance_get_match` requires that result id and resolves evidence only inside it. This prevents a LIVE discovery from being followed by a replay-backed evidence lookup and gives the judge a concrete source-fidelity handle. Result records are bounded and are invalidated on share-state transitions.

Every state-changing tool also requires a stable `request_id`. Exact retries return the previously committed result without reapplying a mutation; reuse with a different payload is rejected. If an execution is cancelled after the write may have committed, the browser checks the committed-operation ledger and then re-reads authoritative product state instead of assuming the cancelled client response means the mutation disappeared. The R10 ledger is in-process by design; R11 owns durable persistence of the same contract.

## Reproduce the R10 gate

The replay demo that served the fixture personas was removed once the live
product existed; the browser tool surface is exercised against the live server
now. From a clean checkout with Python 3.10+:

```bash
python3 -m unittest tests.test_web_server_webmcp -v
python3 -m unittest discover -s tests
node --check demo/ui/main.mjs demo/ui/webmcp_live.mjs
git diff --check
```

**Hosted live product:** `https://resonance-production-cfe3.up.railway.app` — the authenticated R11–R14 stack on PostgreSQL (Railway; see `ops/DEPLOY.md`). The live origin serves the WebMCP tools, the Collaboration panel (intro → accept → private relay messaging) and the product API; the R9 replay visual (`demo/ui/webmcp_server.py`) remains the fixture-backed presentation and runs from the demo server above. Follow the judge flow in `demo/ui/README.md` to discover the tools, start private, prepare and preview a thought, explicitly share it with the returned confirmation token, repeat the share with the same `request_id` to prove idempotency, discover structural matches, pass the returned `result_id` into `resonance_get_match`, verify LIVE/REPLAY source fidelity, revoke consent, confirm old results and discovery fail closed, and exercise cancel/reconcile with a stable operation key.

**Real chats, real content (remote MCP):** the same live origin is also a remote MCP server for the assistant a person already talks to (Claude, Cursor, any Streamable-HTTP client): `https://resonance-production-cfe3.up.railway.app/mcp` — the client is given only that URL and completes standard OAuth 2.1 onboarding (RFC 9728 / 8414 / 7591, PKCE S256, explicit consent page; a manually minted key remains a debug-only fallback). The chat's model extracts the causal structure of the person's *actual* work, Resonance previews it, shares only after explicit approval, then discovers people whose reasoning resonates and relays consent-gated introductions. Connection steps and the tool-by-tool test script are in `ops/CONNECT_MCP.md`; `tests/test_remote_mcp.py` runs two people from two chats end to end.

**Real content through the browser tools:** `resonance_prepare_thought` accepts the agent's extracted `thought` (labelled causal graph) or raw `context` (never retained), exactly like the remote MCP path; without either it falls back to the thought visible on the page. After an explicit share the page's live view shows the person's own thought.

Native WebMCP acceptance is a separate evidence requirement: the browser/agent must actually discover the six registered tools and invoke at least one read flow plus the write/share/retry flow. Static source inspection alone is not reported as proof of native discovery/invocation.

## Provenance for this R10 run

- mission: `R10-WEBMCP-COMPLIANCE` / issue #82
- agent_id: `parshkov-openai-gpt56sol-chat-a91c`
- human sponsor: `Parshkov`
- provider/model: OpenAI / GPT-5.6 Sol
- runtime: ChatGPT web with direct GitHub repository access
- base used for final implementation: current `main` containing the accepted R9 merge; final branch is rebased/reapplied before submission
- blind constraints: none
- mission modification: none; maintainer safe-share, retry-safety, and discovery-source-fidelity review requirements are followed

No credentials, private conversations, private user data, or proprietary third-party material are part of this submission.
