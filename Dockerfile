# Resonance live product server — hosted deployment image (R16 surface).
#
# The server is pure standard-library Python: no requirements file, no build
# step. It needs the repository tree at runtime for three things only:
#   demo/ui/        static page + WebMCP/collaboration modules
#   ops/migrations  schema migrations applied at startup
#   demo/corpus     the accepted R7 seed corpus (create-only import)
#
# State lives in ONE SQLite file under /data; mount a persistent volume there.
# A stable RESONANCE_CONFIRMATION_SECRET (>= 32 bytes) is REQUIRED with a
# persistent DB — the server refuses to start without it, by design, so
# prepared private drafts survive restarts. Never bake the secret into the
# image; inject it as a platform secret.

FROM python:3.12-slim

# Unbuffered logs, no .pyc litter, predictable locale.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8

# The only third-party dependency, and only for PostgreSQL: the binary wheel
# needs no compiler. SQLite deployments work without it.
RUN pip install --no-cache-dir "psycopg[binary]==3.3.5"

# Run as an unprivileged user; /data is the only writable location.
RUN useradd --create-home --uid 10001 resonance \
 && mkdir -p /data \
 && chown resonance:resonance /data

WORKDIR /app
COPY --chown=resonance:resonance . /app

USER resonance
VOLUME ["/data"]

# Platform sets PORT (Fly/Railway/Render all do); PUBLIC_ORIGIN must be the
# exact https origin browsers will use — it is the CSRF/Origin allowlist.
ENV PORT=8080 \
    RESONANCE_DB=/data/live-product.sqlite3 \
    PUBLIC_ORIGIN=

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import os,urllib.request,sys; \
      r=urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/product/health', timeout=4); \
      sys.exit(0 if r.status==200 else 1)"

# `--origin` may be repeated; ops/DEPLOY.md shows how to add a second origin
# (e.g. the platform's default *.fly.dev host alongside a custom domain).
CMD ["sh", "-c", "exec python3 -m src.product.server --host 0.0.0.0 --port \"$PORT\" --db \"$RESONANCE_DB\" --origin \"$PUBLIC_ORIGIN\" $EXTRA_ORIGINS"]
