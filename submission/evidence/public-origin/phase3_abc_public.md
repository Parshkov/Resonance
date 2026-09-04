# Phase 3 — public-origin A/B/C structural test

Resource: https://resonance-production-cfe3.up.railway.app/mcp
Started: 2026-09-04T06:20:49Z  Finished: 2026-09-04T06:21:13Z
Deployment health: `{"ok": true, "mode": "live", "freshness": {"db_generation": 81, "serving_generation": 81, "index_current": true, "engine_snapshot": "f7f839d595712aa5467cc12fd91b19c44ccc944f2f0a415f466b4240f8a05892"}}`

**41/41 steps passed**

| # | step | result | detail |
|---|---|---|---|
| 1 | onboard A (register + PKCE + guest consent + token) | PASS | {} |
| 2 | initialize A | PASS | {} |
| 3 | whoami A returns account | PASS | {} |
| 4 | onboard B (register + PKCE + guest consent + token) | PASS | {} |
| 5 | initialize B | PASS | {} |
| 6 | whoami B returns account | PASS | {} |
| 7 | onboard C (register + PKCE + guest consent + token) | PASS | {} |
| 8 | initialize C | PASS | {} |
| 9 | whoami C returns account | PASS | {} |
| 10 | three distinct accounts | PASS | {"user_ids": ["person-2672f00ddb", "person-318b8c85ff", "person-71d0ada06a"]} |
| 11 | A raw-text prepare (not shared) accepted | PASS | {} |
| 12 | A prepare_thought (structured) -> private draft + confirmation_token | PASS | {} |
| 13 | A share without confirm refused | PASS | {} |
| 14 | A share_thought(confirm=true) -> discoverable | PASS | {} |
| 15 | B prepare_thought (structured) -> private draft + confirmation_token | PASS | {} |
| 16 | B share without confirm refused | PASS | {} |
| 17 | B share_thought(confirm=true) -> discoverable | PASS | {} |
| 18 | C prepare_thought (structured) -> private draft + confirmation_token | PASS | {} |
| 19 | C share without confirm refused | PASS | {} |
| 20 | C share_thought(confirm=true) -> discoverable | PASS | {} |
| 21 | B my_thoughts shows B's session discoverable | PASS | {} |
| 22 | B discover returns result_id | PASS | {} |
| 23 | B discover: A present in matches | PASS | {} |
| 24 | B discover: B (self) absent | PASS | {} |
| 25 | B discover: A ranked above C (or C not accepted at all) | PASS | {"rank_A": 0, "rank_C": null} |
| 26 | B explain_match(result_id, A) ok | PASS | {} |
| 27 | A cannot read B's result (subject isolation -> error) | PASS | {} |
| 28 | C request_intro to A without discovery (observed, no expectation asserted) | PASS | {"observed_error": null, "observed_state": "requested"} |
| 29 | B request_intro -> A created | PASS | {} |
| 30 | B request_intro replay with same request_id is idempotent | PASS | {"replay_intro_id_equal": true, "error": null} |
| 31 | A list_intros shows B's incoming intro | PASS | {} |
| 32 | A respond_intro(accept) -> channel | PASS | {} |
| 33 | A send_message delivered | PASS | {} |
| 34 | B read_messages sees A's message | PASS | {} |
| 35 | C (non-member) cannot read the channel | PASS | {} |
| 36 | A stop_sharing -> revoked | PASS | {} |
| 37 | A whoami no longer lists the session as shared | PASS | {"shared_thoughts": [], "private_thoughts_count": 2} |
| 38 | B discover after revoke: A absent from matches AND rejected | PASS | {} |
| 39 | B explain_match on old result after A revoked (observed) | PASS | {"observed_error": "stale_result"} |
| 40 | cleanup: B stop_sharing | PASS | {} |
| 41 | cleanup: C stop_sharing | PASS | {} |

## B discover #1 (A shared, C shared)

- result_id: `result-21330ad10b4fd06cf06984be` source: `live` contract: `resonance-discovery/0.1`
- order (session ids): `['ses-d1135a3b0d3c0e1e', 'ses-gabe-warehouse', 'ses-jonas-diagnostics', 'ses-lina-scaffold', 'ses-mei-battery-heat', 'ses-omar-chronology']`  rank_A=0 rank_C=None rejected_count=0
- A scores: `{"structural": 0.8875000000000001, "semantic": 0.09659863945578231, "r_direct": 1.0, "y_systematicity": 1.0, "coverage_containment": 1.0, "contradiction": 0.0, "h_sign_conflict": false}`
- C scores: `null`
- A evidence: `{"preserved_relation_count": 7, "top_correspondences": [{"query_node": "b0", "candidate_node": "a0", "query_label": "shortage rumour", "candidate_label": "partial upstream outage"}, {"query_node": "b1", "candidate_node": "a1", "query_label": "synchronized bulk purchasing", "candidate_label": "synchronized client retries"}, {"query_node": "b2", "candidate_node": "a2", "query_label": "demand amplification", "candidate_label": "request amplification"}, {"query_node": "b3", "candidate_node": "a3", "query_label": "empty shelves", "candidate_label": "cascading saturation"}, {"query_node": "b4", "candidate_node": "a4", "query_label": "per-customer purchase cap", "candidate_label": "per-client retry budget"}], "mapped_node_count": 7, "contradiction_count": 0, "preserved_relations": [{"query_relation": "r0", "candidate_relation": "r0"}, {"query_relation": "r1", "candidate_relation": "r1"}, {"query_relation": "r2", "candidate_relation": "r2"}, {"query_relation": "r3", "candidate_relation": "r3"}, {"query_relation": "r4", "candidate_relation": "r4"}]}`
- C evidence: `null`

## Session ids

`{"A": "ses-d1135a3b0d3c0e1e", "B": "ses-fadeaeda06454f9d", "C": "ses-7b29b88cdefd3761"}`

Mcp-Session-Id header observed from server: `{'A': False, 'B': False, 'C': False}`

Full privacy-safe detail: phase3_abc_public.json (pseudonymous ids, no raw context text, no tokens).
