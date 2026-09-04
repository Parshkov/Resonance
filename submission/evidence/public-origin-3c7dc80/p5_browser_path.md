# P5 — browser-path (cookie + CSRF, stdlib) on the public origin (HEAD 3c7dc80)

Origin: https://resonance-production-cfe3.up.railway.app · run 2026-09-04T15:45:28+00:00

NONCE='pulse4-p5' (appended to the implicit prose to keep the thought id fresh; see reservation probe)

resonance_token cookie, csrf_token and confirmation_token values are redacted (only set/missing is recorded).

| UTC | step | status | expected | result | note |
|---|---|---|---|---|---|
| 15:44:55Z | POST /api/product/guest | 200 | 200 | PASS | cookie=set csrf=set |
| 15:45:00Z | POST /api/webmcp/prepare (structured thought, 5 nodes) | 200 | 200 | PASS | input_kind=agent_structured discoverable=False source_retention=not_retained |
| 15:45:01Z | GET /api/webmcp/preview | 200 | 200 | PASS | labels_found=5/5 topic='Panic buying after a shortage rumour' confirmation_token=set |
| 15:45:04Z | POST /api/webmcp/share (confirm=true) | 200 | 200 | PASS | shared=True discoverable=True |
| 15:45:04Z | GET /api/context?source=live -> own thought | 200 | 200 | PASS | topic='Panic buying after a shortage rumour' own_labels=5/5 thought_id=thought-mcp-panic-buying-after-a-shortage-rumour-64bc9d74 shared_with_resonance=True |
| 15:45:05Z | GET /api/context?source=replay -> fixture thought | 200 | 200 | PASS | thought_id=thought-aria-plasma-lens |
| 15:45:13Z | GET /api/discover?source=live | 200 | 200 | PASS | matches=15 contract_version=resonance-discovery/0.1 |
| 15:45:18Z | POST /api/webmcp/consent (shared=false) | 200 | 200 | PASS | revoked=True shared=False discoverable=False |
| 15:45:22Z | POST /api/product/guest (second guest) | 200 | 200 | PASS | fresh identity for the refusal check |
| 15:45:28Z | POST /api/webmcp/prepare (implicit prose context) | 400 | 400 | PASS | error=validation_failed message='no shareable structure could be extracted from the text (0 nodes, 0 relations: no explicit relation cues; implicit structure not emitted). The extractor only follows explicit cues and never invents st' |
| 15:45:28Z | GET /api/webmcp/preview (no draft left) | 409 | 409 | PASS | error=conflict |

## /api/discover?source=live — first three matches

```json
[
 {
  "mode_classification": "approximate",
  "scores": {
   "structural": 0.8829545454545454,
   "semantic": 1.0,
   "r_direct": 1.0,
   "y_systematicity": 1.0,
   "coverage_containment": 1.0,
   "contradiction": 0.0,
   "h_sign_conflict": false
  }
 },
 {
  "mode_classification": "approximate",
  "scores": {
   "structural": 0.8829545454545454,
   "semantic": 1.0,
   "r_direct": 1.0,
   "y_systematicity": 1.0,
   "coverage_containment": 1.0,
   "contradiction": 0.0,
   "h_sign_conflict": false
  }
 },
 {
  "mode_classification": "approximate",
  "scores": {
   "structural": 0.8829545454545454,
   "semantic": 1.0,
   "r_direct": 1.0,
   "y_systematicity": 1.0,
   "coverage_containment": 1.0,
   "contradiction": 0.0,
   "h_sign_conflict": false
  }
 }
]
```

top match keys: ['actions', 'confidence', 'display', 'evidence', 'hard_rejection', 'match_id', 'mode_classification', 'person_pseudonym', 'scores', 'session_id']

**11/11 checks passed**


## Appendix — thought-id reservation probe (browser path, separate guests, NONCE='pulse4-probe')

Context: the first (concurrent) P4/P5 attempt at 15:43Z used the task's exact prose for both the implicit and the cue-explicit context; the MCP-side P4 draft reserved the cue text's thought id and the P5 implicit-prose step then got `409 conflict` ("thought_id is already reserved") instead of `400 validation_failed`. This probe isolates what reserves an id. csrf/cookie values not recorded.

| UTC | step | status | body (trimmed) |
|---|---|---|---|
| 15:44:57Z | guest A: prepare implicit EXACT text (task wording) | 409 | {"error": "conflict", "message": "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id"} |
| 15:45:13Z | guest B: prepare implicit FRESH text (nonce) — 1st time ever | 400 | {"error": "validation_failed", "message": "no shareable structure could be extracted from the text (0 nodes, 0 relations: no explicit relation cues; implicit structure not emitted). The extractor only follows explicit cues and nev |
| 15:45:13Z | guest B: preview after refusal | 409 | {"error": "conflict", "message": "no prepared private draft exists"} |
| 15:45:17Z | guest C: prepare implicit FRESH text again (does a refusal reserve?) | 409 | {"error": "conflict", "message": "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id"} |
| 15:45:21Z | guest D: prepare cue EXACT text (reserved by earlier P4 draft?) | 409 | {"error": "conflict", "message": "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id"} |
| 15:45:27Z | guest E: prepare cue FRESH text — 1st time ever (private draft, never shared) | 200 | {"input_kind": "raw_text_fallback", "discoverable": false, "draft_id": "set", "source_retention": "not_retained"} |
| 15:45:30Z | guest F: prepare cue FRESH text again (does a private draft reserve globally?) | 409 | {"error": "conflict", "message": "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id"} |
| 15:45:30Z | guest E: preview (own draft still there) | 200 | {"draft_id": "set", "source_retention": "not_retained"} |

Reading: (1) the task's exact implicit and cue texts are now globally reserved on this deployment (rows A, D); (2) a never-before-seen implicit text is refused with 400 and leaves no draft (rows B, B-preview) **but the refusal itself reserves the content-derived thought id**: the same text from a fresh guest four seconds later gets 409 rather than 400 (row C); (3) a private, never-shared raw-text draft also reserves its id for every other user (rows E, F). The P4/P5 tables above therefore use nonce-suffixed prose; the expected 400/isError behaviour holds on first use of any text.
