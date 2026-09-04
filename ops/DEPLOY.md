# Deploying the Resonance live product (R16 runbook)

The live product server is one pure-standard-library Python process
(`python3 -m src.product.server`) with no build step. Its only third-party
dependency is the PostgreSQL driver (`psycopg[binary]`), installed by the
`Dockerfile`. State lives in the database you point it at.

## What the process needs

| setting | how it is passed | notes |
| --- | --- | --- |
| database | `--db <path-or-DSN>` | `postgresql://…` selects PostgreSQL; anything else is a SQLite file; `:memory:` is ephemeral |
| confirmation secret | `RESONANCE_CONFIRMATION_SECRET` env (≥ 32 bytes) or `--secret-file` | **required** with a persistent DB — the server refuses to start without it so prepared private drafts survive restarts. Never put it on the command line or in the image. |
| browser origin allowlist | `--origin https://your.host` (repeatable) | must be the **exact** `https://` origin browsers will use; this is the CSRF/Origin check. Add a second `--origin` for a platform default host alongside a custom domain. |
| bind address / port | `--host 0.0.0.0 --port $PORT` | the image reads `PORT` from the platform |
| seed | default seeds the accepted R7 corpus (create-only, idempotent across restarts); `--no-seed` starts empty | |

Migrations under `ops/migrations/` are applied automatically at startup on both
backends. Health: `GET /api/product/health` → `{"ok": true, ...}`.

HTTPS is mandatory for the WebMCP browser surface (secure context); every
platform below terminates TLS in front of the container.

## Verified before this runbook was written

On PostgreSQL 16.13, from a clean database, executed in a real browser
(headless Chromium, two separate cookie jars) against the server started with
exactly the command in the `Dockerfile`:

- all three migrations apply and the R7 seed loads (25 sessions);
- the full #86 human-UI scenario passes — B clicks **Request intro**, A
  **Accept**s, A opens the channel and **Send**s, B reads the message;
- after killing and restarting the process: users, sessions, the accepted
  intro, the channel and the message all persist, the seed does not duplicate,
  and the discovery index rebuilds to `index_current: true`.

Two fixes were required for PostgreSQL to work at all. The first landed on
`main` as `457506b` (the `;` inside a comment in `0001_init.sql` broke the very
first migration; fixed in the migration, with a hygiene test). The second is
part of the same change as this runbook: `build_runtime` hard-wired SQLite, so a
DSN passed via `--db` was treated as a file name and the live product could not
run on PostgreSQL regardless of the migration fix. Cookies are marked `Secure`
automatically when every allowed origin is `https://`.

## Option A — Fly.io with Fly Postgres (recommended: one CLI, ~10 minutes)

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

## Option B — Railway (GUI, no CLI; built-in Postgres)

1. New Project → **Deploy from GitHub repo** → pick this repository. Railway
   detects the `Dockerfile`.
2. **+ New → Database → PostgreSQL.** Railway exposes `DATABASE_URL` to the
   service.
3. Service → **Variables**:
   - `RESONANCE_DB` = `${{Postgres.DATABASE_URL}}`
   - `RESONANCE_CONFIRMATION_SECRET` = a 64-hex random string
   - `PUBLIC_ORIGIN` = the `https://…up.railway.app` URL from **Settings →
     Networking → Generate Domain** (do that first)
4. Deploy. Check `https://<domain>/api/product/health`.

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

## Known limits at the time of writing

- The R9 visual discovery view (map, match cards) does not initialise on the
  live origin — see #88. The collaboration panel and every product API work.
- One process, one machine: fine for the ≥100-user pilot on the accepted
  structural engine; scale-out would need sticky sessions or a shared
  idempotency store, neither of which the pilot requires.
- Backups: use the platform's Postgres snapshots (Fly: `fly postgres backup`,
  Railway/Render: dashboard). SQLite deployments must snapshot the volume.
