# Resonance live product server — hosted deployment image (R16 surface).
#
# The server is standard-library Python apart from the PostgreSQL driver: no
# requirements file, no build step. It needs the repository tree at runtime for
# three things only:
#   demo/ui/        static page + WebMCP/collaboration modules
#   ops/migrations  schema migrations applied at startup
#   demo/corpus     the R7 demo corpus (seeded only with RESONANCE_SEED_DEMO=1)
#
# State lives in PostgreSQL, which is the ONLY store Resonance runs on: set
# RESONANCE_DB to the DSN (production reads it from the platform). The image
# holds no state and needs no volume.
#
# This header used to say "state lives in ONE SQLite file under /data", and set
# a SQLite path as the default RESONANCE_DB. That has been untrue since the
# hosted deployment moved to PostgreSQL — production overrode the variable, so
# the wrong default never bit, but it did mislead a reader into believing the
# product ships on SQLite. There is no SQLite backend any more.
#
# A stable RESONANCE_CONFIRMATION_SECRET (>= 32 bytes) is REQUIRED with a
# persistent DB — the server refuses to start without it, by design, so
# prepared private drafts survive restarts. Never bake the secret into the
# image; inject it as a platform secret.

FROM python:3.12-slim

# Unbuffered logs, no .pyc litter, predictable locale.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8

# The only third-party dependency: the PostgreSQL driver. The binary wheel
# needs no compiler. It is required, not optional -- there is no other store.
RUN pip install --no-cache-dir "psycopg[binary]==3.3.5"

# The label encoder (src/semantics/neural.py): a small multilingual sentence
# encoder run locally through onnxruntime. Optional at build time -- pass
# --build-arg RESONANCE_EMBEDDER_MODEL=Xenova/multilingual-e5-small to bake
# it in -- and switched on at run time with RESONANCE_EMBEDDER=/models/e5.
# Without it the engine reads labels with the English lexicon only.
ARG RESONANCE_EMBEDDER_MODEL=
RUN if [ -n "$RESONANCE_EMBEDDER_MODEL" ]; then \
      pip install --no-cache-dir "onnxruntime>=1.17" "tokenizers>=0.15" \
   && mkdir -p /models/e5/onnx \
   && python3 -c "import urllib.request,sys; base='https://huggingface.co/'+sys.argv[1]+'/resolve/main/'; \
        [urllib.request.urlretrieve(base+p, '/models/e5/'+p) for p in ('tokenizer.json','onnx/model_quantized.onnx')]" \
        "$RESONANCE_EMBEDDER_MODEL" \
   && chmod -R a+rX /models; fi

# Run as an unprivileged user; /data is the only writable location.
RUN useradd --create-home --uid 10001 resonance \
 && mkdir -p /data \
 && chown resonance:resonance /data

WORKDIR /app
COPY --chown=resonance:resonance . /app

USER resonance
# No Docker VOLUME instruction: Railway rejects it ("use Railway Volumes"), and
# the app container holds no state -- everything durable is in PostgreSQL.

# Platform sets PORT (Fly/Railway/Render all do); PUBLIC_ORIGIN must be the
# exact https origin browsers will use — it is the CSRF/Origin allowlist.
# RESONANCE_SEED_DEMO=1 seeds the 25 labelled demo personas (demo/corpus) into
# the database at start; unset (default) the product starts with real
# participants only. `python3 -m src.persistence --db "$RESONANCE_DB" purge-demo`
# removes previously seeded demo state.
# RESONANCE_DB has no default on purpose: it must be the deployment's own
# PostgreSQL DSN, and a wrong default is worse than a startup error.
ENV PORT=8080 \
    RESONANCE_DB= \
    PUBLIC_ORIGIN= \
    RESONANCE_SEED_DEMO= \
    RESONANCE_EMBEDDER=

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import os,urllib.request,sys; \
      r=urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/product/health', timeout=4); \
      sys.exit(0 if r.status==200 else 1)"

# The web server is the live product handler plus the browser presentation
# routes (/api/context, /api/discover) and the browser WebMCP module, so a
# visitor gets the visual discovery view AND the six registered tools on their
# own authenticated state. `--origin` may be repeated; ops/DEPLOY.md shows how
# to add a second origin (a platform default host alongside a custom domain).
# RESONANCE_ENTRYPOINT=src.product.server selects the API-only server instead.
CMD ["sh", "-c", "exec python3 -m ${RESONANCE_ENTRYPOINT:-src.product.web_server} --host 0.0.0.0 --port \"$PORT\" --db \"$RESONANCE_DB\" --origin \"$PUBLIC_ORIGIN\" $EXTRA_ORIGINS"]
