# Card B — real hosted Claude MCP client on the public origin (executed 2026-09-04 ≈16:35 UTC)

**Client.** The repository owner's claude.ai org has a custom connector named
`Resonance` (installed server `d444b748-…`, `installState: connected`,
`isAuthless: false`, i.e. it authenticated through the server's own OAuth) whose
tools were loaded into a Claude Code cloud session. That session made the calls
below through Anthropic's hosted MCP client against
`https://resonance-production-cfe3.up.railway.app/mcp` (deployment `6ec0959e`,
code `9b51262`). No manual key, no sandbox HTTP: only the connector.

| Card B step | executed by | result |
| --- | --- | --- |
| 1–3 add connector at the canonical `/mcp` URL, OAuth discovered, consent, tools listed | owner (claude.ai UI) — outcome visible to the session as `connected` + twelve `resonance_*` tools | PASS |
| 4 `resonance_whoami` | this session | `user_id: person-b1bd2e2c90bc3c51`, `display_label: guest-9aadc1`, `actor_type: agent`, one shared thought, `index_current: true` |
| 5–6 prepare + approved share | already done on this account at 15:12:06–15:12:29 UTC (`share_state: discoverable`, `record_kind: volunteer`, `provenance.kind: manual`, `source.text: ""` = raw text not retained) — **not repeated here** because sharing needs the person's explicit approval in the chat | executed earlier on the same account; not re-executed |
| 7 `resonance_discover` (k=5) | this session | `result-19790231e038d12d3964071b`, `source: live`, 8 rows in backend order (ties share a rank, so k is a rank bound, not a row cap), 1 rejected; no contact details, `location_note` present |
| 7 `resonance_explain_match` on the first row | this session | same match object with mapped nodes and preserved relations (below) |
| 8 `resonance_stop_sharing` | **not executed** — would change the owner's live share state without their explicit approval | skipped on purpose |

## whoami (verbatim, pseudonymous ids only)

```json
{"contract_version":"resonance-remote-mcp/0.1","user_id":"person-b1bd2e2c90bc3c51","display_label":"guest-9aadc1","actor_type":"agent","shared_thoughts":["ses-099c77441b96db62"],"private_thoughts":[],"freshness":{"db_generation":275,"serving_generation":275,"index_current":true,"engine_snapshot":"97432dc7b4902bb898d76a73896a41f258c018571d4edd325df111e311cd78b3"}}
```

## my_thoughts (structure of the shared thought)

`thought-mcp-irrigation-retry-storms-after-pressure-drops-5452a55b`, topic
"Irrigation retry storms after pressure drops", domain `irrigation-systems`;
7 nodes (agent `irrigation controllers`, problem `irrigation cycle failure`,
outcome `plants miss watering`, constraint `no new hardware allowed`, states
`pipe overload` / `brief water pressure drop`, mechanism `simultaneous controller
retries`), 7 relations (`causes` ×5, `supports`, `constrains`); consent
`share_thought_dna: true`, `share_coarse_location: false`,
`allow_intro_requests: true`.

## discover → first row (verbatim scores/evidence)

```json
{"match_id":"88ce4c46f8d7100093c4b407","person_pseudonym":"guest-69fe20","session_id":"ses-a95528cc2a90ef11","mode_classification":"negative","hard_rejection":null,
 "scores":{"structural":0.7339285714285715,"semantic":0.2571428571428572,"r_direct":0.7142857142857143,"y_systematicity":1,"coverage_containment":1,"contradiction":0.14285714285714285,"h_sign_conflict":false},
 "confidence":"provisional",
 "evidence":{"mapped_node_count":7,"preserved_relation_count":5,"contradiction_count":1,
  "top_correspondences":[{"query_label":"irrigation controllers","candidate_label":"order workers"},{"query_label":"irrigation cycle failure","candidate_label":"delivery queue failure"},{"query_label":"plants miss watering","candidate_label":"missed customer deliveries"},{"query_label":"no new hardware allowed","candidate_label":"no new servers allowed"},{"query_label":"pipe overload","candidate_label":"queue overload"}],
  "preserved_relations":[["r0","r0"],["r1","r1"],["r2","r2"],["r3","r3"],["r4","r4"]]},
 "display":{"share_state":"discoverable","cluster_id":"retry-storm-overloads-delivery-queue","topic":"Retry storm overloads delivery queue","domain":"distributed-systems"},
 "actions":["compare","explain","request_intro"]}
```

Other rows: four identical `Retry and outage observability` thoughts from
guests `e43c23`, `9d9df9`, `40111e`, `bfe661` (structural 0.206 — these are the
R15D hosted-client probe fixtures still shared on production), seed corpus rows
`Mei L.` / `Noah R.` (0.674, 4 preserved relations, 0 contradictions) and
`Priya S.` (0.275); `Dev K.` hard-rejected (`direction:r3->r1`) and listed under
`rejected`, not among matches. `explain_match` returned the first row unchanged
with `source: live` and the same freshness.

## Honest scope

- Proves: OAuth-onboarded hosted Claude client → production `/mcp` → identity,
  own-thought listing, live discovery with structural evidence, per-match
  explanation. Card B steps 1–4 and 7 executed from a real Anthropic client.
- Does not prove: a share approved inside a claude.ai chat UI in this run (the
  account's share predates the session), `stop_sharing` from this client,
  ChatGPT (Card C), or native `document.modelContext` (Card A).
- Observation for the owner: the top structural match (0.734, 5/7 relations
  preserved) is classified `negative` because one relation contradicts; the
  page's fallback rule therefore still renders it as an approximate resonance.
