# P3 — re-prepare regression (same raw `context` twice) on the public origin (HEAD 9b51262)

Origin: https://resonance-production-cfe3.up.railway.app · MCP: https://resonance-production-cfe3.up.railway.app/mcp · run 2026-09-04T16:15:08+00:00

Context text: the exact three-sentence retry-storm paragraph specified for this pulse (no nonce). Access/refresh tokens, authorization codes, confirmation tokens, the resonance_token cookie, csrf_token and recovery_secret are never printed.

| UTC | step | status | expected | result | note |
|---|---|---|---|---|---|
| 16:14:54Z | G1 onboarded via OAuth (guest) + initialize + whoami | ok | user_id | PASS | user=person-005e3fc543089244 |
| 16:14:56Z | G1 prepare #1 (raw context) | ok | ok, relations>=1 | PASS | draft_id=draft-c5a167b1b19d20bea50d6ddd relations=4 nodes=7 input_kind=raw_text_fallback confirmation_token=set |
| 16:14:57Z | G1 share (confirm=true + token) | ok | ok, discoverable=true | PASS | session_id=ses-92c373f3360477d4 |
| 16:14:58Z | G1 stop_sharing (confirm=true) | ok | ok | PASS | keys=['contract_version', 'discoverable', 'revoked', 'session_id', 'shared'] |
| 16:15:00Z | G1 prepare #2 (SAME exact context, after stop_sharing) — regression | ok | ok (previously 409 thought_id already reserved) | PASS | draft_id=draft-c730773c487cfef8601dae2f relations=4 |
| 16:15:00Z | G1 draft_id #2 != draft_id #1 | - | different | PASS | draft-c5a167b1b19d20bea50d6ddd vs draft-c730773c487cfef8601dae2f |
| 16:15:04Z | G2 onboarded via OAuth (guest), distinct user | ok | user_id != G1 | PASS | user=person-7e7f78d35969f0e0 |
| 16:15:05Z | G2 prepare (SAME exact context) — regression | ok | ok | PASS | draft_id=draft-0d9d3220bb24365ec9c2869c relations=4 |
| 16:15:05Z | G2 draft_id differs from G1's two drafts | - | different | PASS | draft-0d9d3220bb24365ec9c2869c |
| 16:15:07Z | browser: POST /api/product/guest | 200 | 200 + cookie + csrf | PASS | cookie=set csrf=set |
| 16:15:08Z | browser: POST /api/webmcp/prepare (SAME exact context) | 200 | 200 | PASS | draft_id=draft-b2de4f92dfa06f22ec01a047 input_kind=raw_text_fallback discoverable=False error=None |
| 16:15:08Z | browser draft_id differs from the three MCP drafts | - | different | PASS |  |
| 16:15:08Z | browser: POST /api/webmcp/consent shared=false | skipped | n/a | n/a | never shared on this path; not needed |

## draft_id equality

| pair | equal? |
|---|---|
| G1 #1 vs G1 #2 | False |
| G1 #1 vs G2 | False |
| G1 #2 vs G2 | False |
| MCP drafts vs browser | False |

**12/12 checks passed**

