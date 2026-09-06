# Resonance

**Find the people whose reasoning has the same shape as yours — computed, not judged.**

Live at **<https://resonance.parshkov.com>**, with a remote MCP endpoint at `/mcp`
for chat clients.

Resonance represents a thought as a typed causal graph, compares those graphs
structurally, and shows you the working: which of your ideas corresponds to
which of theirs, which relations are preserved, where you contradict each other,
and how confident the match is. No language model decides who resonates with
you.

---

## The problem

We look for people through job titles, biographies, social graphs and keywords —
and we are often wrong. Not because anyone behaved badly, but because we confuse
shared vocabulary with shared reasoning, and shared profession with shared
interest.

Resonance asks whether part of that can become **observable**. Instead of "who
has a similar profile?", it asks:

> Whose current thought has a structure that meaningfully resonates with mine?

```text
thought → structured signal → resonance → person
```

rather than `person → profile → demographic similarity → connection`.

## Thought is not text

Two texts can share almost every word and express different reasoning. Two
thoughts can share no vocabulary at all and have the same shape:

```text
battery                         organization
  → heat accumulation             → information accumulation
  → degradation                   → coordination degradation
  → failure                       → failure
```

Different nouns, different domains — an embedding places them far apart. But the
relational pattern is the same: *a system, an accumulating intermediary effect,
degradation of function, failure.*

So a thought is stored as a **Thought Graph**: typed nodes (problem, method,
mechanism, constraint, evidence, outcome, …) and typed relations (causes,
prevents, requires, supports, contradicts, …), specified in
[`docs/THOUGHT_DNA_v0.1.md`](docs/THOUGHT_DNA_v0.1.md) and frozen as
[`schemas/thought-dna-0.1.schema.json`](schemas/thought-dna-0.1.schema.json).

## What it detects

Five verdicts, and the engine returns exactly one:

| verdict | meaning |
|---|---|
| `direct` | the same reasoning about the same subject |
| `approximate` | related, but partial, noisier or differently decomposed — including someone working on **one piece** of your problem |
| `analogical` | a different domain, the same abstract structure, slot for slot |
| `complementary` | not the same thought; one holds a branch or method the other lacks |
| `negative` | no structural resonance, whatever the words suggest |

Sometimes the person you need is not the one who already thinks like you. It is
the one whose thought **begins where yours ends**.

---

## How it works

Two stages, deliberately separate: cheap recall, then expensive proof.

```text
prose, or a graph supplied by an agent
   ↓  src/extraction — cue extractor, no LLM
Thought DNA v0.1  ·  validated, canonically hashed
   ↓  src/fingerprint — structural + concept keys
inverted multi-channel index with IDF  (src/index)
   ↓  over-fetched candidates
FGW alignment + scoring policy v0.2   (src/alignment, src/scoring)
   ↓  verified ranking
explanation: correspondences, preserved relations, contradictions, confidence
```

**Retrieval proposes; verification ranks.** A match is not "0.83 similar" — it is
a mapping you can read, and the page draws it.

### A language model is not the matching engine

An LLM can turn prose into a graph and put a result into words. It does not
decide the result. Alignment, scoring and classification are ordinary code with
inspectable thresholds, so a verdict is reproducible and does not move when a
vendor ships a new model.

Label semantics come from a hand-written lexicon of abstract relational concepts
(`src/semantics`, ~90 classes, English and Russian). Beside it sits an **optional
local sentence encoder** ([ADR-0006](docs/decisions/ADR-0006-label-encoder.md),
`RESONANCE_EMBEDDER`) that reads labels the lexicon cannot — it raises signals
the lexicon already gives and can never manufacture an analogy on its own. The
hosted deployment runs with it on.

### Foundations

Structure-Mapping Theory, for the distinction between surface similarity and
relational analogy; MAC/FAC, for cheap recall followed by expensive structural
verification; Weisfeiler–Lehman-style graph fingerprints for the retrieval keys;
Fused Gromov-Wasserstein for alignment under differing size and vocabulary. The
decisions that survived, with the evidence under them, are in
[`docs/decisions/`](docs/decisions/).

---

## What is proven, and what is not

The honest state is [`docs/STATUS.md`](docs/STATUS.md). In short:

**Measured** on Benchmark v0.2 — 8 distinct reasoning skeletons × 4 domains × 18
case families, with the S5–S8 gate split kept separate from calibration:

- same words, different structure → rejected;
- different words, same abstract structure → `analogical`;
- the same skeleton with concept-free labels (a template coincidence) → `negative`;
- partial, paraphrased, permuted, granular and extraction-noisy variants →
  retrieved and classified correctly;
- prose with explicit connectives → a grounded graph with no LLM.

**Not established:**

- **The comparison this project rests on has never been run.** A whole-thought
  embedding baseline is what [`WHY_NOT.md`](WHY_NOT.md) rejects and what
  ADR-0004 names as the condition for reconsidering — and no one has measured it.
- Benchmark gold is agent-authored; independent human review is pending, so
  `classification_accuracy = 1.0` means "no regression", not "generalises".
- Real thoughts at scale: the live corpus is small, and every benchmark graph is
  authored rather than extracted from a real conversation.
- Scale: query time is linear from ~350 graphs upward, not sub-linear.
- One classification question is deliberately left open rather than tuned away
  ([ADR-0005](docs/decisions/ADR-0005-same-vocabulary-cross-domain-verdict.md)).

---

## Run it

Resonance runs on PostgreSQL everywhere, including its tests, so the store under
test is the store that ships. One container is the whole setup.

```bash
docker run -d --name resonance-pg -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=resonance_test -p 55432:5432 postgres:16

python3 -m src.product.web_server --db :ephemeral: --host 127.0.0.1 --port 8830 \
    --origin http://127.0.0.1:8830 &
python3 ops/populate_local.py http://127.0.0.1:8830 /tmp/people.json
open http://127.0.0.1:8830/
```

`:ephemeral:` is a throwaway schema; point `--db` at a `postgresql://…` DSN for a
real database. Deployment is [`ops/DEPLOY.md`](ops/DEPLOY.md).

### Tests and gates

```bash
pip install "psycopg[binary]"
python3 -m unittest discover -s tests        # 682 tests
python3 benchmark/r0-v0.2/runner.py          # engine gate, exit 0
python3 benchmark/extraction-v0.2/runner.py  # extraction gate, exit 0
python3 ops/lexicon_check.py                 # a lexicon change is additive
```

Benchmark gold is frozen: a branch may not make itself pass by editing it, and
CI fails if it changes.

### Connect a chat client

Add a remote MCP server at `https://resonance.parshkov.com/mcp` with no
credentials. The client discovers the authorization server, registers itself,
and opens the consent page in your browser; sign in there and it is connected.
21 `resonance_*` tools — the same vocabulary the page registers in the browser
through WebMCP, so a chat agent and a browser agent speak one language.
Details in [`ops/CONNECT_MCP.md`](ops/CONNECT_MCP.md).

**Nothing becomes discoverable without an explicit confirmation step.** An
assistant prepares a thought privately, you see exactly what would be shared,
and only then does it become searchable. Your conversation is never sent to the
service.

---

## Repository

```text
src/
  graph/        Thought DNA model, validation, canonical hashing
  semantics/    lexicon, stemmer, similarity, optional label encoder
  extraction/   prose → Thought Graph, no LLM
  fingerprint/  structural and concept retrieval keys
  index/        inverted multi-channel candidate index
  alignment/    FGW / RRWM structural verification
  scoring/      component formulas, classification policy, confidence
  interfaces/   the frozen boundaries the engine talks through
  engine/       the composed facade
  ── the product, which depends on the engine and never the reverse ──
  discovery/    consented, visualization-ready read model
  ingestion/    private prepare → preview → explicit share
  identity/     accounts, sessions, consent, pseudonyms
  persistence/  the PostgreSQL repository, migrations, projection
  security/     fail-closed authorization kernel, audit, rate limits
  collaboration/ intro state machine and private relay
  workspaces/   multi-person workspaces and shared topics
  product/      HTTP server, MCP tool vocabulary, presentation
  remote/       OAuth 2.1 core and the remote MCP entry point

demo/ui/        the page: screens over one state store
benchmark/      frozen falsification fixtures — gate split never used for tuning
ops/            deployment, migrations, acceptance probes
docs/           status, threat model, privacy, and the accepted ADRs
history/        how the project was built, and why — see history/README.md
```

**Entry points:** [`docs/STATUS.md`](docs/STATUS.md) for what is true today ·
[`docs/decisions/`](docs/decisions/) for why the engine is shaped this way ·
[`WHY_NOT.md`](WHY_NOT.md) for approaches deliberately rejected ·
[`PRINCIPLES.md`](PRINCIPLES.md) for the rules the project holds itself to.

## Privacy

Raw conversation text is never sent to the service and never stored. What is
shared is the structure you confirm. People are shown to each other under
pseudonyms; an introduction happens only when both sides agree, and revoking a
thought removes it from discovery immediately.
[`docs/PRIVACY_AND_DATA_USE.md`](docs/PRIVACY_AND_DATA_USE.md) ·
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) ·
[`SECURITY.md`](SECURITY.md)

## History

Resonance was built in eight days as a public experiment in human–agent
collaboration: missions claimed through GitHub Issues by independent agents on
different models, some deliberately blind to each other, with every submission,
review and rejected method committed. That phase is complete and the record is
in [`history/`](history/) — it is not maintained and is not an instruction.

## License

Apache-2.0 — [`LICENSE`](LICENSE).
