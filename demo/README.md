# demo/

Two things live here.

## `demo/ui/` — the page

The browser interface of the live product: six screens over one state store,
served by `src.product.web_server`. See [`ui/README.md`](ui/README.md).

## `demo/corpus/` — the labelled demo corpus

Twenty-five labelled personas wrapping accepted Thought DNA with consent and
presentation metadata. Seeded into an ephemeral PostgreSQL schema by default
(so a local run has people in it) and into a persistent one only with
`--seed-demo` / `RESONANCE_SEED_DEMO=1`. Demo personas are shown as examples,
never introduced, and never told about anyone. See
[`corpus/README.md`](corpus/README.md).

The stdio MCP client and server that first proved the engine end to end (R6)
were retired once the remote MCP server and the page existed; their record is
under [`archive/hackathon/`](../archive/hackathon/).
