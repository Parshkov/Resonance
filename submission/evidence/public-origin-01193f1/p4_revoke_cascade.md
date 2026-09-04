# P4 — refresh-token revoke cascade on the public origin

Origin: https://resonance-production-cfe3.up.railway.app/mcp · HEAD 01193f1 · run 2026-09-04T15:13:56Z

Statuses only; tokens, codes and verifiers are never printed.

| UTC | step | status | expected | result | note |
|---|---|---|---|---|---|
| 15:13:57Z | unauthenticated POST /mcp (ping) | 401 | 401 | PASS |  |
| 15:13:57Z | dynamic client registration | 201 | 201 | PASS |  |
| 15:13:58Z | GET /oauth/authorize (scope=resonance offline_access) | 200 | 200 | PASS |  |
| 15:13:59Z | consent POST -> redirect | 302 | 302 | PASS |  |
| 15:13:59Z | token exchange (authorization_code) | 200 | 200 | PASS | scope='resonance offline_access' has_refresh=True |
| 15:13:59Z | initialize with access token | 200 | 200 | PASS |  |
| 15:14:00Z | tools/call resonance_whoami with access token | 200 | 200 | PASS | user_id=person-… |
| 15:14:00Z | tools/list with access token (pre-revoke) | 200 | 200 | PASS | tools=12 |
| 15:14:00Z | POST /oauth/revoke (refresh_token) | 200 | 200 | PASS |  |
| 15:14:01Z | refresh grant with revoked refresh token | 400 | 400 | PASS | error=invalid_grant |
| 15:14:01Z | tools/list with OLD ACCESS token after refresh revoke (cascade) | 401 | 401 | PASS | www-authenticate=present |
| 15:14:01Z | fresh initialize with OLD ACCESS token after cascade | 401 | 401 | PASS |  |

12/12 checks passed

exit=0
