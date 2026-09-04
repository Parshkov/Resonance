# Resonance — WebMCP Challenge Devpost Draft

> **STATUS: PRE-SUBMISSION DRAFT.** Replace every `TBD` only with evidence from the frozen release candidate. Do not submit text that implies a feature is live before its acceptance gate passes.

## One-line description

**Resonance helps people discover other people whose ideas share the same underlying reasoning structure — then, with mutual consent, lets their agents help them collaborate.**

## Inspiration / problem

Today, search systems are excellent at finding similar words, topics, documents, and embeddings. But two ideas can use completely different vocabulary and still depend on the same causal or relational pattern. Conversely, two people can use the same words for very different reasons.

Resonance asks a different question:

> Has anyone else reasoned in a structurally similar way, even in another domain?

The project represents a user-approved idea as a versioned **Thought DNA** graph, compares structural relationships rather than surface wording, and returns evidence showing why two sessions resonate.

## What it does

Canonical product flow for the submitted release:

1. A user works in the Resonance web experience with an AI agent.
2. The agent prepares a structured Thought DNA candidate from user-selected context.
3. **Preparation is private.** The user sees a share preview and explicitly approves what becomes discoverable.
4. Resonance persists the approved session and consent state.
5. A browser agent invokes Resonance through **WebMCP**.
6. Resonance searches the consented corpus using its accepted structural engine.
7. The page updates with 2–4 evidence-backed matches, coarse consented geography, and a visual resonance map.
8. The user can inspect the structural mapping explaining a match.
9. In the complete product release, a user can request an introduction; the other person must explicitly accept before private collaboration begins.
10. Accepted connections can continue in a private multi-person idea workspace with notes, tasks, messages, and artifacts. Authorized agents act only within their user's permissions.

### Two transports, honestly separated

- **Browser WebMCP (competition eligibility):** the page registers native `document.modelContext` tools; a browser agent invokes them and the page visibly updates. On the current build the browser `resonance_prepare_thought` builds from the labelled flagship page thought — it does **not** silently receive the user's ChatGPT conversation.
- **Remote MCP from a real LLM chat (the cross-chat product):** an external LLM client passes the real selected conversation context to `resonance_prepare_thought(context=…)` over authenticated remote MCP; Resonance privately extracts Thought DNA, previews/shares it, and discovers against another independently ingested user's chat. This is submitted as **R15 (PR #128), pending review** — presented as a submitted extension, not claimed as live, unless accepted and deployed before freeze.

**Accepted gates as of this packaging pass** (each independently reviewed and merged to `main`; verify against the frozen SHA before submit):

| gate | what it adds | status |
| --- | --- | --- |
| R10 WebMCP compliance | six browser-native `document.modelContext` tools | accepted |
| R11 persistence | durable multi-user store (PostgreSQL/SQLite) | accepted |
| R12 identity/consent | pseudonymous accounts, per-session consent | accepted |
| R12B security | one authorization kernel, CSRF/rate/audit | accepted |
| R12C ingestion | private prepare → preview → explicit share | accepted |
| R13 live product | authenticated DB-backed discovery + map | accepted |
| R13B rich results | structured result + consent-safe visuals | accepted |
| R14 collaboration | intro state machine + private relay messaging | accepted |
| R14B workspaces | multi-person idea rooms, roles, shared work | accepted |
| R16 deployment | hosted HTTPS on Railway + PostgreSQL | live at the URL above |
| R15 remote MCP | authenticated remote MCP for external agents | **submitted (PR #128), pending review — do not claim as live until accepted** |

The competition demo and write-up should describe only the accepted/live gates; R15 remote-MCP is presented as a submitted extension, not a live judged feature, unless it is accepted and deployed before freeze.

## Why WebMCP matters

WebMCP is not a wrapper around our existing stdio MCP. It is the browser-native interaction layer for the competition experience.

The live Resonance page registers browser tools through `document.modelContext.registerTool(...)`. That lets a capable browser/agent understand and invoke product actions directly in the page while keeping the human-visible UI and product state synchronized.

Expected submitted browser tool flow (verify exact names against frozen release):

- `resonance_prepare_thought`
- `resonance_get_share_preview`
- `resonance_share_prepared_thought`
- `resonance_discover`
- `resonance_get_match`
- `resonance_update_consent`
- collaboration/workspace tools only if accepted in the release

WebMCP improves the UX because the agent does not need to guess DOM clicks or scrape UI state. Tools have explicit schemas, read/write semantics, consent boundaries, and visible effects in the same application the user is looking at.

## What is technically distinctive

### Structural rather than semantic retrieval

Resonance compares typed/directed relationships, roles, constraints, polarity, causal/dependency structure, and evidence mappings. Display metadata and location are presentation-only and do not change structural ranking.

### Evidence instead of a similarity number alone

Matches include backend-derived structural evidence explaining which concepts and relationships correspond. Contradictions/hard rejections are kept separate from resonances.

### Privacy-first social discovery

- private by default;
- prepare != share;
- explicit per-session sharing;
- coarse location only when separately consented;
- no private contact information before mutual acceptance;
- revocation removes live discoverability;
- private collaboration state is member-only;
- other-user content is treated as untrusted content for agents.

### One product state, multiple agent surfaces

The target architecture uses one authenticated product/service layer for human UI, WebMCP, local development MCP, and remote MCP. Remote MCP, if included in the frozen release, is an additional interoperability path — **not** a substitute for WebMCP.

## How we built it

The repository records a staged engineering process with explicit claims, submissions, independent reviews, deterministic fixtures, regression tests, and provenance. The accepted stack includes Thought DNA contracts, extraction, retrieval, structural alignment/verifier logic, MCP transport, a consent-aware demonstration corpus, discovery contracts, and the competition visual client.

During the WebMCP challenge period the project is extending that research/demo stack into a hosted multi-user product with browser WebMCP, durable persistence, identity/consent, collaboration, security/data governance, and deployment/release verification.

See `HACKATHON.md` in the frozen release for the exact pre-existing-vs-challenge-period breakdown.

## Challenges

The hard problem is not drawing a map. It is maintaining one consistent set of invariants across structural matching, user consent, durable state, browser agents, remote agents, and collaboration:

- metadata must not contaminate structural ranking;
- revoked users must not leak through stale indexes or map aggregates;
- retried agent writes must not double-create state;
- user-generated content from another person must remain untrusted to an agent;
- all transports must enforce the same authenticated authorization decisions.

## Accomplishments we are proud of

Use only items verified in the frozen release. Candidate list:

- deterministic cross-domain structural matches with mapping evidence;
- explicit contradiction/hard-rejection handling;
- consent-aware discovery and hidden-user non-leakage;
- polished 1920×1080 competition UI with genuine LIVE/REPLAY parity;
- real browser WebMCP invocation;
- durable multi-user persistence and revocation safety;
- privacy-safe intro and multi-person collaboration;
- structured + rich visual agent results;
- reproducible public release with independent clean-checkout/live-URL verification.

## What we learned

Context is important evidence, but it is not always the thing we ultimately want to match. Two people can reach the same answer through different reasoning, while different domains can share the same underlying relational topology. Exposing that distinction safely to AI agents requires both a structural engine and unusually explicit consent/authorization boundaries.

## What's next

The competition release is a pilot, not a claim of a global social network. Future work may include larger volunteer corpora, stronger extraction/calibration, production-grade identity and moderation, broader agent interoperability, richer collaborative workspaces, and evaluation on real-world scientific/engineering discovery workflows.

Long-term question:

> **Has anyone, anywhere, reasoned like this before?**

## Links — fill from frozen candidate

- Live application: `https://resonance-production-cfe3.up.railway.app` (Railway, PostgreSQL-backed; judge path in `HACKATHON.md`)
- Public repository: `https://github.com/Parshkov/Resonance`
- Demo video (<3:00, public YouTube): `TBD`
- Frozen release/tag: `TBD`
- Judge instructions: `TBD`

## Final truthfulness checklist

Before copying this text to Devpost:

- [ ] every described live feature exists in the frozen candidate;
- [ ] real browser WebMCP invocation has independent evidence;
- [ ] WebMCP and remote MCP are described distinctly;
- [ ] no population-scale claim exceeds the actual pilot;
- [ ] no security/privacy claim exceeds implemented controls;
- [ ] known benchmark/calibration limitations remain documented;
- [ ] live URL/repo/video/tag are final and public;
- [ ] Apache-2.0 is visible on GitHub;
- [ ] no confidential/private user information appears here or in screenshots/video.
