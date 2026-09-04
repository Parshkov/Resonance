# P4: WebMCP discover on a never-shared guest (public origin, HEAD bd161ad)

UTC: Fri Sep  4 06:35:17 UTC 2026

## Guest creation
POST https://resonance-production-cfe3.up.railway.app/api/product/guest  (Origin: https://resonance-production-cfe3.up.railway.app, body {})
status: 200
resonance_token cookie set: yes
body (redacted): {"user_id": "person-d565cafa578f0739", "csrf_token": "<redacted>", "expires_at": "2026-09-11T06:35:17.145924Z", "recovery_secret": "<redacted>"}

## GET /api/webmcp/discover?source=replay (with cookie)
status: 409
body: {"error": "share_required", "message": "discovery needs a shared thought first: run resonance_prepare_thought → resonance_get_share_preview → resonance_share_prepared_thought (explicit confirm), then resonance_discover again."}

## GET /api/webmcp/discover?source=live (with cookie)
status: 409
body: {"error": "share_required", "message": "discovery needs a shared thought first: run resonance_prepare_thought → resonance_get_share_preview → resonance_share_prepared_thought (explicit confirm), then resonance_discover again."}

## Verdict
PASS: both sources return 409 share_required (previously 500)
