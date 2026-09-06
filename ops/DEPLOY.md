# Deploying the Resonance live product (R16 runbook)

The live product server is one pure-standard-library Python process
(`python3 -m src.product.server`) with no build step. Its only third-party
dependency is the PostgreSQL driver (`psycopg[binary]`), installed by the
`Dockerfile`. State lives in the database you point it at.

## What the process needs

| setting | how it is passed | notes |
| --- | --- | --- |
| database | `--db <DSN>` | a `postgresql://…` DSN. Resonance runs on PostgreSQL only; `:ephemeral:` makes a throwaway schema on the development/test server (local development and tests) |
| confirmation secret | `RESONANCE_CONFIRMATION_SECRET` env (≥ 32 bytes) or `--secret-file` | **required** with a persistent DB — the server refuses to start without it so prepared private drafts survive restarts. Never put it on the command line or in the image. |
| browser origin allowlist | `--origin https://your.host` (repeatable) | must be the **exact** `https://` origin browsers will use; this is the CSRF/Origin check. Add a second `--origin` for a platform default host alongside a custom domain. |
| bind address / port | `--host 0.0.0.0 --port $PORT` | the image reads `PORT` from the platform |
| retire unsigned accounts | `RESONANCE_PURGE_UNSIGNED=report` counts and prints; `=1` carries it out. Tombstones every session whose owning account has no verified sign-in behind it, and revokes those accounts. `RESONANCE_PURGE_KEEP=<id>[,<id>…]` spares named sessions or accounts. A signed-in account is never touched, and a second run finds nothing left to do. Run `report` first, read the counts in the deploy log, then `=1`, then unset. | one-shot operator action |
| label encoder | `RESONANCE_EMBEDDER=<directory>` holding `tokenizer.json` and `onnx/model_quantized.onnx` (multilingual-e5-small, exported to ONNX; ~135 MB) plus the `onnxruntime` and `tokenizers` packages | **recommended.** Without it the semantic layer is the hand-written English lexicon, which is blind to most real vocabulary and to every other language: the same trip described twice in different words came back "not a resonance". With it, each label is embedded locally on the CPU (about 6 ms a pair, cached), and the cosine adds relatedness the lexicon could not see; structure, contradiction and the verdict are unchanged. The server refuses to start if the variable names a directory it cannot load, and `/api/product/health` reports `engine.label_encoder`. Build the image with `--build-arg RESONANCE_EMBEDDER_MODEL=Xenova/multilingual-e5-small` to bake the model in. |
| sign-in providers | `RESONANCE_AUTH_GOOGLE_CLIENT_ID` / `RESONANCE_AUTH_GOOGLE_CLIENT_SECRET`, and/or `RESONANCE_AUTH_GITHUB_CLIENT_ID` / `RESONANCE_AUTH_GITHUB_CLIENT_SECRET` | **required for a real deployment.** Setting either pair turns on sign-in, and sign-in then becomes the *only* way an account is created: `POST /api/product/guest` answers `403 sign_in_required`, and the OAuth consent page offers no anonymous option. With neither pair set the pseudonymous guest path stays on — that is the local-development and test configuration, not a production one. Callback URL to register with the provider: `https://<your origin>/auth/callback/google` (and `/auth/callback/github`). Scopes requested are only `openid email profile` / `read:user user:email`. |
| how mail leaves | This platform blocks outbound SMTP below its Pro plan, and its own documentation says so: "SMTP is only available on the Pro plan and above... Free, Trial, and Hobby plans must use transactional email services with HTTPS APIs", with Resend named as the recommended one. Measured here before that was found: ports 587, 465 and 25 all time out on IPv4, and IPv6 is off by default so every AAAA answers "network is unreachable". So set `RESONANCE_MAIL_API_KEY` (and `RESONANCE_MAIL_FROM`) and mail goes out over 443, the same door the site is served from. `RESONANCE_MAIL_API_URL` defaults to Resend's endpoint; Postmark and Mailgun differ only in field names. The `RESONANCE_SMTP_*` path still works where SMTP is allowed, and an API key wins over it wherever both are set. | |
| prove mail works | `RESONANCE_MAIL_SELFTEST=you@example.com` sends exactly one message to that address at startup and prints the outcome, then you unset it. `/api/product/health` can only say the variables are set; this says the message arrived. Run it before inviting anyone, because the alternative is finding out from someone who waited for a notification that never came. | one-shot operator action |
| notifications | `RESONANCE_MAIL_API_KEY` and `RESONANCE_MAIL_FROM` (or, where SMTP is allowed, `RESONANCE_SMTP_HOST` / `_PORT` / `_USER` / `_PASSWORD`) turn on the email that tells someone a resonance appeared while they were away — the half of the promise that happens after they leave. `RESONANCE_MAIL_REPLY_TO` (default: `RESONANCE_CONTACT`) is where a reply lands, because a technical sender must not be a dead end. With none of these set nothing is sent, nothing is queued, and `health.notifications.can_reach_people` is false. | |
| what is set up on parshkov.com | Resend, Ireland (eu-west-1), sending as `pulse@parshkov.com`, verified 2026-09-05. Three DNS records were added at the registrar and nothing else was touched: `CNAME send -> send.forge.rmta.net`, `CNAME rsend -> rsend-euw1.forge.rmta.net`, `TXT resend._domainkey`. **The inbound MX record Resend also offers was deliberately NOT added**: the apex MX is Google Workspace, and pointing it at Resend would silently take delivery of every message to the domain. The root SPF is untouched for the same reason -- Resend's return path is the `send.` subdomain, which carries its own SPF, so DKIM at `resend._domainkey` is what aligns the apex, and it does, in relaxed mode, under the existing `p=quarantine`. Click and open tracking are off: click tracking rewrites every link, including the signed one-click unsubscribe. | |
| demo purge | `RESONANCE_PURGE_DEMO=1` runs `purge-demo` once at process start (tombstones seeded demo sessions, revokes demo persona accounts, never touches `volunteer` rows; idempotent) and logs the counts. Set it, let the platform redeploy, confirm `purge-demo: sessions_deleted=…` in the deploy log and `corpus.demo_personas_present: false` in `/api/product/health`, then unset it. | one-shot operator action |
| demo seed | **off by default** for any persistent database (real participants only). `--seed-demo` or `RESONANCE_SEED_DEMO=1` seeds the 25 labelled R7 demo personas (create-only, idempotent); `python3 -m src.persistence --db <DSN> purge-demo` tombstones seeded demo sessions and revokes the persona accounts. `:memory:` is always seeded (local dev/tests). | `purge-demo` ran on production 2026-09-04 19:13 UTC via `RESONANCE_PURGE_DEMO=1`: 0 sessions, 0 users (no demo rows were present) |

> **The platform's start command wins over the Dockerfile.** Railway keeps a
> per-service start command in its own settings, and it overrides `CMD`. Worse,
> *redeploying* reuses the previous deployment's captured configuration, so
> editing that setting and pressing redeploy changes nothing. After renaming or
> moving the entrypoint module you must both update the platform's start command
> **and** trigger a genuinely new deployment (a push, not a redeploy). Renaming
> `competition_server` to `web_server` cost several failed deploys this way: the
> container exited with `No module named src.product.competition_server`, the
> health check failed, and the platform silently kept serving the previous
> release — so the site looked merely stale rather than broken.

Migrations under `ops/migrations/` are applied automatically at startup on both
backends (`0005_oauth_grants` makes OAuth codes / refresh grants / client
registrations durable, so a redeploy no longer forces hosted MCP clients to
re-authorize). Health: `GET /api/product/health` → `{"ok": true, ...}`.

HTTPS is mandatory for the WebMCP browser surface (secure context); every
platform below terminates TLS in front of the container.

## Verified before this runbook was written

On PostgreSQL 16.13, from a clean database, executed in a real browser
(headless Chromium, two separate cookie jars) against the server started with
exactly the command in the `Dockerfile`:

- all three migrations apply and (when `RESONANCE_SEED_DEMO=1`) the R7 demo seed loads (25 sessions);
- the full #86 human-UI scenario passes — B clicks **Request intro**, A
  **Accept**s, A opens the channel and **Send**s, B reads the message;
- after killing and restarting the process: users, sessions, the accepted
  intro, the channel and the message all persist, a demo seed does not duplicate,
  and the discovery index rebuilds to `index_current: true`.

Two fixes were required for PostgreSQL to work at all. The first landed on
`main` as `457506b` (the `;` inside a comment in `0001_init.sql` broke the very
first migration; fixed in the migration, with a hygiene test). The second is
part of the same change as this runbook: `build_runtime` hard-wired the old store, so a
DSN passed via `--db` was treated as a file name and the live product could not
run on PostgreSQL regardless of the migration fix. Cookies are marked `Secure`
automatically when every allowed origin is `https://`.

## Option A — Railway with Railway PostgreSQL (chosen: no CLI, ~10 minutes, ~$8–12/month)

**Production is provisioned this way** as project `resonance-live`, origin
`https://resonance-production-cfe3.up.railway.app` (2026-09-04). Lessons from
that first real build, so nobody repeats them:

- Railway has **deprecated config-as-code** (`railway.json` / `railway.toml`)
  and defaults to the Railpack builder. Set **Dockerfile path**, **healthcheck
  path** (`/api/product/health`, 60 s) and **restart policy** (on failure) in
  the service's *Settings* — the file in the repo is documentation only.
- Railway **rejects a Docker `VOLUME` instruction** ("use Railway Volumes"); the
  Dockerfile no longer has one.
- The PostgreSQL service runs the `pgvector/pgvector:pg16` image with a
  Railway volume at `/var/lib/postgresql/data` and
  `PGDATA=/var/lib/postgresql/data/pgdata`; `DATABASE_URL` points at the
  private host `postgres.railway.internal:5432`.
- Health-check success is Railway's own probe of `/api/product/health`, i.e.
  migrations applied (and, only when requested, the demo seed loaded) before traffic is routed.
- **Push auto-deploy is ON since 2026-09-04 16:30 UTC.** Until then it could
  not even be toggled (`canEnable: false, reason: NO_INSTALLATION`): the
  service was linked to `Parshkov/Resonance` by name only and the Railway
  GitHub App was not installed on the repository, so every deployment was
  started by hand. Fix that worked: the repository owner installed the Railway
  GitHub App on `Parshkov/Resonance`, then the source was re-linked from the
  Railway plugin (`connect-service-source` repo `Parshkov/Resonance`, branch
  `main`), after which Railway reports
  `{"enabled": true, "canEnable": true}` and the service source records
  `branch: main`. If auto-deploy ever stops firing again, check those two
  things in that order (App installed on the repo → source shows the branch).
  A manual deploy is still possible from the plugin or the dashboard.
- **Volume backups.** On 2026-09-04 a `DAILY` backup schedule was set on volume
  `postgres-data` through Railway's agent (`updateVolumeTool`, result
  `staged`). The API cannot read the schedule back, so confirm in the
  dashboard: Postgres service → volume `postgres-data` → **Backups** should
  show the daily schedule and, after the first run, a completed backup. Until
  someone has seen a completed backup there, treat the database as
  **unbacked-up**.
- **Entrypoint is `src.product.web_server`** (the image default, and set
  explicitly as the Railway start command): the live product handler plus the
  browser presentation routes and the browser WebMCP module, so the public
  page shows the visual discovery view on real data and registers the six
  tools. `RESONANCE_ENTRYPOINT=src.product.server` runs the API-only server.

1. **Create the project.** railway.com → **New Project** → **Deploy from GitHub
   repo** → `Parshkov/Resonance`, branch `main`. Railway detects the Dockerfile.
   The first deploy will fail on purpose (no secret yet) — that is expected.
2. **Add PostgreSQL.** In the project canvas: **+ Create** → **Database** →
   **Add PostgreSQL**. Wait until it shows a green status. It exposes
   `DATABASE_URL` (and an internal `postgres.railway.internal` URL) to the
   project.
   - pgvector (optional, for later): the standard Railway PostgreSQL image
     ships the extension — once the DB is up, open its **Data** tab (or
     **Connect** → `psql`) and run `CREATE EXTENSION IF NOT EXISTS vector;`.
     If the image lacks it, deploy the **pgvector** template from the Railway
     catalog instead and point `RESONANCE_DB` at that service.
   - Backups: open the PostgreSQL service → **Backups** and confirm daily
     volume backups are enabled on your plan; if not, add a `pg_dump` cron
     service later.
3. **Generate the public URL first.** Click the app service → **Settings** →
   **Networking** → **Generate Domain**. Copy the `https://….up.railway.app`
   URL — it is needed for the origin allowlist in the next step.
4. **Variables.** App service → **Variables** → **+ New Variable** (or **Raw
   Editor**):

   | variable | value |
   | --- | --- |
   | `RESONANCE_DB` | `${{Postgres.DATABASE_URL}}` (reference the DB service; use the private URL variant if offered — no egress cost) |
   | `RESONANCE_CONFIRMATION_SECRET` | 64 random hex characters, e.g. from `openssl rand -hex 32` or any password generator; must be ≥ 32 bytes and **never change afterwards** |
   | `PUBLIC_ORIGIN` | the exact `https://….up.railway.app` from step 3, no trailing slash |

   `PORT` is injected by Railway automatically; the image reads it.
5. **Deploy.** Saving variables triggers a redeploy. Watch **Deployments →
   View logs** for `live product on http://0.0.0.0:<port> (... mode: LIVE)`.
   The health check must go green before traffic is routed.
6. **Smoke test** (below). Then open the URL in Chrome and run the judge flow
   from `HACKATHON.md`.

Custom domain later: **Settings → Networking → Custom Domain**, add the CNAME
Railway shows, then set `PUBLIC_ORIGIN=https://your.domain` and
`EXTRA_ORIGINS="--origin https://….up.railway.app"` so both hosts pass the
origin check. Never leave a host out of the allowlist: browsers on it will be
CSRF-rejected on every write.

## Option B — Fly.io with Fly Postgres (CLI, ~10 minutes, ~$5–8/month; unmanaged Postgres)

```bash
fly auth login
fly launch --no-deploy --copy-config --name resonance-live --region ams
fly postgres create --name resonance-live-db --region ams --vm-size shared-cpu-1x --initial-cluster-size 1
fly postgres attach resonance-live-db          # injects DATABASE_URL
fly secrets set RESONANCE_CONFIRMATION_SECRET="$(openssl rand -hex 32)"
fly secrets set PUBLIC_ORIGIN="https://resonance-live.fly.dev"
fly deploy
fly logs                                       # expect: "live product on http://0.0.0.0:8080 (... mode: LIVE)"
curl -s https://resonance-live.fly.dev/api/product/health
```

`fly.toml` mirrors `DATABASE_URL` into the `--db` argument, so no extra wiring.
Custom domain: `fly certs add your.domain`, then set
`PUBLIC_ORIGIN=https://your.domain` and `EXTRA_ORIGINS="--origin https://resonance-live.fly.dev"`
so both hosts pass the origin check.

## Option C — Render (managed Postgres, `render.yaml` not included)

Web Service from the repo (Docker), plus a **PostgreSQL** instance. Set the same
three variables; Render provides the internal connection string. Note the free
web tier sleeps on idle, which is fine for judging but not for a pilot.

## Option D — any VPS with Docker

```bash
docker build -t resonance-live .
docker run -d --name resonance --restart unless-stopped -p 127.0.0.1:8080:8080 \
  -e PORT=8080 \
  -e RESONANCE_DB="postgresql://user:pass@db-host:5432/resonance" \
  -e RESONANCE_CONFIRMATION_SECRET="$(openssl rand -hex 32)" \
  -e PUBLIC_ORIGIN="https://your.domain" \
  resonance-live
```

Put Caddy (or nginx + certbot) in front for HTTPS:

```
your.domain {
    reverse_proxy 127.0.0.1:8080
}
```

## Smoke test after any deploy

```bash
ORIGIN=https://your.domain
curl -s "$ORIGIN/api/product/health"                     # ok: true
curl -s -X POST "$ORIGIN/api/product/guest" -H 'Content-Type: application/json' \
     -H "Origin: $ORIGIN" -d '{}' -c /tmp/c.txt          # returns csrf_token + sets cookie
```

Then open `$ORIGIN/` in Chrome and run the judge flow from `HACKATHON.md`.

## Canonical MCP OAuth on the production origin (R15C, #136)

A hosted MCP client (Claude, ChatGPT, Cursor…) that is given only
`https://<origin>/mcp` must be able to authorize through the browser — no
manual MCP key, bearer, capability URL or custom header in the normal path.
Production wiring for that lives in `src/product/oauth_mount.py`; the protocol
core itself is `src/remote/**` (R15A, #134) and is attached to the runtime as
`runtime.oauth_core`.

What the origin serves once the core is attached:

| path | purpose |
| --- | --- |
| `POST /mcp` without a valid bearer | `401` + `WWW-Authenticate: Bearer realm="resonance", resource_metadata="<issuer>/.well-known/oauth-protected-resource"` (RFC 9728) |
| `GET /.well-known/oauth-protected-resource` | resource = `<issuer>/mcp`, `authorization_servers` = `[<issuer>]` |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 metadata: authorize / token / register / revoke endpoints, `S256`, grant types |
| `GET /oauth/authorize` | browser consent page (login or continue as guest, explicit consent), PKCE + `state` + `redirect_uri` validated before any redirect |
| `POST /oauth/authorize` | same-site form submit → `302` to the exact `redirect_uri` with `code` + `state` |
| `POST /oauth/token`, `/oauth/register`, `/oauth/revoke` | token exchange / refresh, RFC 7591 client registration, revocation |

Issuer: the process only ever sees plain HTTP behind the platform proxy, so the
absolute issuer is `PUBLIC_ORIGIN` (the single `https://` allowed origin); the
fallbacks are `X-Forwarded-Proto`/`X-Forwarded-Host` (Railway always sets both)
and then `Host`. Nothing in the OAuth core reads `Host` itself. The identity
cookie stays `SameSite=Strict`: the cross-site arrival at `GET /oauth/authorize`
carries no cookie, the consent form's own POST does, so the grant binds to the
browser account the person already uses on the site when one exists.

Smoke from any machine that can reach the origin (never prints tokens):

```bash
python3 ops/oauth_smoke.py https://<origin>/mcp          # human pastes the callback URL
python3 ops/oauth_smoke.py http://127.0.0.1:8788/mcp --auto-consent   # local
```

Human test card (starts with the `/mcp` URL only, no secret ever typed):

1. In your MCP client add a remote server with URL `https://<origin>/mcp` and no credentials.
2. The client discovers the authorization requirement by itself (no error about a missing key).
3. Your browser opens the Resonance authorization page on `https://<origin>/oauth/authorize…`.
4. Sign in with your recovery secret, or continue as guest.
5. Read the consent screen and approve.
6. The browser returns you to the client; the client reports Resonance as connected.
7. The client lists Resonance tools (12 `resonance_*` tools).
8. Ask the assistant to call `resonance_whoami`: it returns your pseudonymous `user_id` and display label.

The manual MCP key path (Collaboration panel → **Create MCP key**, or
`/mcp/<key>`) remains available as a debug fallback only.

## Known limits at the time of writing

- The page (`/thoughts`, `/people`, `/talk`, `/groups`, `/connect`) needs the
  browser routes that `src.product.web_server` serves (`/api/product/overview`,
  `/api/discover`, the topic routes); the API-only `src.product.server` serves
  the document but the screens cannot load their data there.
- One process, one machine: fine for the ≥100-user pilot on the accepted
  structural engine; scale-out would need sticky sessions or a shared
  idempotency store, neither of which the pilot requires.
- Backups: use the platform's Postgres snapshots (Fly: `fly postgres backup`,
  Railway/Render: dashboard).
