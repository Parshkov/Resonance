# R10 WebMCP provenance

- mission: `R10-WEBMCP-COMPLIANCE`
- issue: `#82`
- agent_id: `parshkov-openai-gpt56sol-chat-a91c`
- human_sponsor: `Parshkov`
- provider: OpenAI
- model: GPT-5.6 Sol
- runtime: ChatGPT web
- canonical claim comment: `5503394436`
- claim verification / protocol-transparency comment: `5503471716`
- safe-share scope update followed: `5503179519`
- retry-safety scope update followed: `5503440850`
- maintainer source-fidelity review followed: PR #97 comments `5503584943` / `5503612671`
- blind group: none
- mission modified: no

## Boundary

R10 is a browser WebMCP transport and competition-compliance layer over the accepted R9 visual client and accepted R8 discovery contract. It does not implement, tune, or fork matching/retrieval/verifier/scoring semantics. The browser receives consent-safe product projections and the same accepted discovery evidence/order used by the human UI.

The state-changing browser path is deliberately private-first and retry-safe:

- prepare creates a non-discoverable draft;
- preview is read-only and returns an opaque HMAC confirmation token;
- explicit share requires both `confirm=true` and the current token;
- revocation invalidates stale preview tokens and fails discovery closed;
- every write requires a stable `request_id` idempotency key;
- exact duplicate writes return the existing committed result;
- a key reused with different input is rejected;
- a cancelled/lost-response write can be reconciled through the committed-operation ledger, after which the UI is refreshed from authoritative `/api/webmcp/state` rather than optimistic client state.

Read provenance is also explicit. Each `resonance_discover` call stores a bounded exact result record and returns an opaque `result_id`. `resonance_get_match` requires that id and resolves the requested session only from that exact payload; it reports the bound `live`/`replay` source and never silently reloads the replay fixture. Revocation or a newly shared prepared thought clears retained result ids so evidence cannot cross a consent/thought-state transition.

The R10 operation ledger and discovery-result store are intentionally in-process and single-user. R11/R12/R12B own durable persistence, authenticated identity/authorization, retention, abuse controls, and deployment-grade security. R10 does not claim those later guarantees.

## Evidence discipline

Only checks actually executed by this run are reported as passing. This runtime does not provide a WebMCP-capable interactive browser. Native browser tool discovery/invocation must therefore be independently reproduced on the final exact PR head before canonical `SUBMIT` / acceptance.

The run executes syntax/layer checks for the exact changed modules plus local HTTP harnesses for safe share, idempotent duplicate writes, cancel/reconcile, and discovery-result source fidelity. Those checks are implementation evidence but are explicitly not substituted for the required native browser gate.
