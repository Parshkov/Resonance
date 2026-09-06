# P5 — browser-style real-content prepare on the public origin (cookie + CSRF, stdlib)

Origin: https://resonance-production-cfe3.up.railway.app · HEAD 01193f1 · run 2026-09-04T15:14:01Z

csrf_token, resonance_token cookie and confirmation_token values are redacted (only set/missing is recorded).

| UTC | step | status | expected | result | note |
|---|---|---|---|---|---|
| 15:14:03Z | POST /api/product/guest | 200 | 200 | PASS | cookie=resonance_token:set csrf=set user_id=person-… |
| 15:14:04Z | POST /api/webmcp/prepare (agent_structured) | 200 | 200 | PASS | input_kind=agent_structured discoverable=False source_retention=not_retained draft_id=set |
| 15:14:05Z | GET /api/webmcp/preview | 200 | 200 | PASS | labels_found=5/5 presentation.topic='Panic buying after a shortage rumour' presentation.domain='consumer-economics' confirmation_token=set currently_shared=False |
| 15:14:07Z | POST /api/webmcp/share (confirm=true) | 200 | 200 | PASS | shared=True discoverable=True |
| 15:14:08Z | GET /api/webmcp/discover?source=live | 200 | 200 | PASS | result_id=set matches=12 top_structural_score=0.8829545454545454 top_topic='' |
| 15:14:10Z | POST /api/webmcp/consent (shared=false) | 200 | 200 | PASS | revoked=True shared=False discoverable=False |
| 15:14:10Z | POST /api/webmcp/prepare (negative: bad role, no ids) | 400 | 400 | PASS | error=validation_failed |

top match keys: ['actions', 'confidence', 'display', 'evidence', 'hard_rejection', 'match_id', 'mode_classification', 'person_pseudonym', 'scores', 'session_id']

7/7 checks passed

exit=0
