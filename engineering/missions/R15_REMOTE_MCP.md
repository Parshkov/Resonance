# R15-REMOTE-MCP — run record

- mission: #87
- canonical agent: `dima2010-anthropic-fable5-7328` (Anthropic / Claude Fable 5)
- run_id: `R15-REMOTE-MCP-F5`
- base: accepted main `499b336` (R14B merged)

## What this run adds

`src/remote/` rebuilt on the accepted `LiveProductService` (the foundation
PR #93 scaffold's transport framing kept; its R7-fixture service, global session
set, and caller-selected demo identity deleted). This closes every recorded
#93 completion blocker:

- **Live durable subject-scoped state** — `RemoteProductService` is a thin
  adapter; every tool resolves to a `LiveProductService` method over the durable
  R11/R12/R13 state. No R7 fixture, no matching/scoring in the transport.
- **Bearer = accepted R12 access token** — there is no separate token directory;
  `identity.authenticate(bearer)` resolves the subject, so remote MCP, WebMCP,
  the human UI and local stdio all authenticate through one identity model.
- **Protocol session bound to the subject** — an `Mcp-Session-Id` created at
  `initialize` is bound to the authenticating subject; a request whose bearer
  resolves to a different subject (or none) is refused immediately.
- **OAuth 2.1 code + PKCE tied to R12** — `/oauth/authorize` authenticates
  through R12 (`login` with recovery secret, or a fresh guest) and issues a
  single-use S256 code bound to the resulting R12 access token; `/oauth/token`
  returns that token. Demo-grade scope declared (no consent UI, no refresh, no
  discovery metadata).
- **Strict body bound** — `MAX_BODY_BYTES` before dispatch; oversize → 413 and
  the server survives (transport-survival regression).
- **Full write + collaboration + workspace surface** — 15 tools:
  whoami; prepare / get_share_preview / share_thought / update_consent (R12C);
  discover / get_match (R13B rich, structuredContent + EmbeddedResource SVG);
  request_intro / list_requests / respond_intro / send_message / read_messages
  (R14); create_workspace / get_workspace / list_workspaces (R14B). Writes
  require `confirm`; reads carry `readOnlyHint`; any returned user text carries
  `untrustedContentHint`.

## Cross-transport parity

`resonance_discover` over remote MCP returns byte-identical match ids / order /
scores to `LiveProductService.rich_discover` for the same authenticated subject
and session (regression) — the transports converge on one service.

## Real external-chat ingestion (URGENT REVISION)

The canonical product story, proven executably: a human's **real chat context**
is passed to `resonance_prepare_thought(context=...)` over remote MCP, extracted
into Thought DNA, shared, and discovered against another **independently
ingested** user's chat — no R7 fixture is ever a query or a match.

- `tests.test_remote_mcp.RealChatIngestionTests` builds the corpus with
  `seed=False` and ingests only hand-written raw chat text (no `r7_dna` /
  `QUERY_DNA`). Alice's chat A and Bob's chat B share a causal *structure*
  (input → accumulation → collapse; a control prevents it and requires a signal)
  in **disjoint vocabulary**; Bob's `resonance_discover` returns Alice as an
  **analogical** match with backend evidence bound to the `result_id`.
- **Structure over keywords**: a third chat C reuses A's vocabulary in a
  scrambled structure and is *not* an analogical match — proving structural
  ranking, not keyword coincidence.
- **Raw not retained**: the stored Thought DNA has an empty `source.text`
  (sha256 of empty), and no full raw sentence survives in the durable store; the
  extracted node/relation labels are the consented structure the privacy
  contract keeps.
- Subject isolation (Bob cannot discover from Alice's session) and restart
  persistence (a second service over the same durable repo still discovers)
  hold on the real-chat path.
- Ambient corpus note: a handful of independent real chats give the accepted
  MULTI retrieval its distributional mass (its small-N cold-start behaviour is a
  documented limitation, not this scenario's subject); every corpus row is real
  chat text, never an R7 fixture.

## Evidence

`tests.test_remote_mcp` (9): bearer-required + OAuth/PKCE happy path; PKCE
wrong-verifier + single-use replay rejected; session bound to subject
(cross-subject refused); unknown session + GET 405; full remote journey with the
rich SVG result; confirmation-gated writes as tool errors; cross-transport
parity; body-bound 413 + transport survival; source scan (live product, not
fixture; R12 identity, not a token directory).

```
python3 -m unittest tests.test_remote_mcp -v
python3 -m src.remote.server            # http://127.0.0.1:8899/mcp
python3 -m unittest discover -s tests
```
