# Canonical domain live + corpus duplicates removed — `resonance.parshkov.com` @ `616b7d9`

Two §13 owner actions closed in one sitting, both executed on production and both
measured before and after.

- **Origin (canonical):** https://resonance.parshkov.com · **MCP:** …/mcp
- **Origin (platform host, still valid):** https://resonance-production-cfe3.up.railway.app
- **Commit:** `616b7d9621f191f5b48c08eed86f0c17137fb548` (runtime identical to `8670568`;
  the two deploys since then changed only environment variables)
- **Railway:** project `670bcce5-…` / service `resonance` `172aa183-…` / env `production` `da338ecd-…`
- **Purge deployment:** `50ff6f61-5a88-4dc0-af11-a44389d17dc9`
- **Custom domain:** `da441e84-969b-4ddf-8a13-1e193ecad0e6`

## 1. The duplicates are gone, and the result moved

`RESONANCE_PURGE_SESSIONS` (#172) was set with exactly the ten ids from
`public-origin-0aea577/SUMMARY.md`, the deploy ran the hook, and the variable was
removed again. The startup log, verbatim:

```
purge-sessions: requested=10 deleted=10 already_deleted=0 missing=0
  (ses-bb2d935993bb38c5=deleted, ses-9583f257ab7acd0c=deleted, ses-c041572ff069dafd=deleted,
   ses-ef6d5093f53a09d5=deleted, ses-f141cc4c7a1e1fdb=deleted, ses-e1771799a599ed59=deleted,
   ses-9ef6e59df883a8da=deleted, ses-1e48f4558db17120=deleted, ses-4eea2164ed2bccbb=deleted,
   ses-5a8a8932b46be630=deleted)
  (RESONANCE_PURGE_SESSIONS set; unset it after this deploy)
```

Every id accounted for: 10 requested, 10 deleted, nothing missing, nothing already gone.
`corpus.volunteer_sessions` 67 → **57**. `ses-a95528cc2a90ef11` and `ses-099c77441b96db62` —
the A/A' pair the inventory said to keep — were not in the list and are untouched.

**The measured effect, which is the point:**

| | before (`8670568`) | after |
|---|---|---|
| A ("retry storm") found by B ("panic buying") | `rank=4`, score 1.0 | **`rank=0`**, score 1.0 |
| matches returned to B | 12 | 4 |
| A vs C (shared vocabulary, no shared structure) | `rank_A=4`, `rank_C=11` | `rank_A=0`, `rank_C=3` |
| abc_mcp_test | 36/36 | 36/36 |

The genuine cross-domain analogy — the result the product exists to demonstrate — was
sitting behind three exact copies of the query's own thought, each scoring structural 1.0.
It is now first. `score_C` is unchanged at `0.177`, so nothing about scoring moved; only
the duplicates left.

## 2. The custom domain is live — and why it took an hour

`resonance.parshkov.com` serves a real certificate:

```
subject: CN=resonance.parshkov.com
issuer:  C=US; O=Let's Encrypt; CN=YE2
TLSv1.3, ALPN h2
```

**What was actually wrong, recorded because it is a trap anyone would fall into:**
Railway requires **two** DNS records for a custom domain, and its API reports only one.
`list-domains` and `domain-status` returned the `CNAME` with
`status: DNS_RECORD_STATUS_PROPAGATED` and `requiredValue == currentValue`, which reads as
"DNS is complete". The **`TXT _railway-verify.resonance` ownership record was missing and
is not mentioned anywhere in the API response.** Only the dashboard's "Show DNS records"
dialog lists both with per-record status. Until that TXT record existed, the domain stayed
in `VALIDATING_OWNERSHIP`, the edge answered "Not Found", and 443 served the wildcard
`CN=*.up.railway.app`.

Lesson for the next person: for a Railway custom domain stuck in `VALIDATING_OWNERSHIP`,
do not trust the API's DNS summary — open the UI.

Final DNS at the authoritative nameserver:

```
resonance.parshkov.com.                CNAME ositddso.up.railway.app.
_railway-verify.resonance.parshkov.com. TXT  "railway-verify=…"
```

### Both origins keep their own identity

`PUBLIC_ORIGIN` is the custom domain; `EXTRA_ORIGINS` keeps the platform host in the
allowlist. Each host publishes metadata naming **itself**:

```
https://resonance.parshkov.com/.well-known/oauth-protected-resource
  -> resource: https://resonance.parshkov.com/mcp
https://resonance-production-cfe3.up.railway.app/.well-known/oauth-protected-resource
  -> resource: https://resonance-production-cfe3.up.railway.app/mcp
```

So a hosted client already registered against the platform URL keeps its grant and does
not have to re-authorize. The custom domain is the published address, not a forced move.

## 3. Full acceptance against the canonical domain

| check | result | artefact |
|---|---|---|
| `GET /api/product/health` | ok, `resonance-engine/0.2`, `demo_personas_present: false`, volunteer 57 | `health.json` |
| `ops/oauth_smoke.py …/mcp --auto-consent` | **27/27** | `oauth_smoke.txt` |
| `ops/hosted_onboarding_probe.py --smoke --refresh --revoke` | **9/9 required** | `hosted_onboarding_probe.{json,txt}` |
| `abc_mcp_test.py …/mcp` | **36/36**, all guests revoked, `still_discoverable=[]` | `abc.{json,txt}` |
| Card A, Chrome 152 + `--enable-features=WebMCP` | **24/24, `mode: NATIVE`** | `card-a-browser/` |

Card A on the new host additionally confirms the browser registers the tools under the new
origin: `getTools()` reports `origin: https://resonance.parshkov.com`.

The precise card assertion (#171) again passes for the right reason:
`cards=0 expected=0 from 2 returned (0 eligible; classifications=['negative'])`,
`data-state='empty'`, `2 returned · 0 resonances · 0 rejected`.

## Deviations / not claimed

- Cards B, C, D, E remain **unexecuted** and are not claimed.
- `RESONANCE_DB` and `RESONANCE_CONFIRMATION_SECRET` were neither read nor modified.
  `RESONANCE_SEED_DEMO` was never set. `RESONANCE_PURGE_SESSIONS` was set once and removed.
- Session counts grow with every acceptance run even though each run revokes what it
  created: revoked rows are not deleted rows. After this set, `volunteer` is above 57 again
  for that reason, with nothing of it discoverable.
- No tokens, codes or raw text in this directory.
