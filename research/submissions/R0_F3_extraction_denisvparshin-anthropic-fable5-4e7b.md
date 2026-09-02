---
mission: R0-F
run: F3 (independent repeat, REPEAT_CLAIM)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  The canonical R0-F submission (PR #31) and the F2 repeat (PR #32) were NOT
  read. Unavoidable exposure: their issue/PR titles ("span-grounded staged
  extraction contract", "grounded context-to-Thought-Graph extraction
  contract"), seen during board-state determination. Those titles reveal the
  canonical approach's gist, and this report also recommends span-grounded
  staged extraction — that headline convergence must NOT be counted as
  independent. Convergence/divergence on taxonomy sizes, the two-pass
  agreement-core mechanism, reliability ratings, and the validation gates may
  be counted. Same-agent note: one of eight sequential runs by one agent in
  one session (order H2, A2, F3, ...); my own runs anchor each other.
---

# Decision

One-pass free-form extraction is the single largest reliability risk in the
whole architecture and must be rejected. Recommended: a **staged, span-grounded
extraction contract with a two-pass agreement core**. Stages: (1) proposition
segmentation; (2) node extraction into a deliberately small taxonomy (6 types),
every node carrying source spans; (3) edge extraction into a closed 7-type
vocabulary with polarity, every edge citing a span; (4) deterministic
canonicalization (lemmatized labels, stable serialization order, skeleton
rendering); (5) schema validation with hard rejection of uncited elements;
(6) the same pipeline run **twice** (fresh runs, temperature 0), and the
intersection of the two outputs becomes the high-confidence **core graph**,
with symmetric-difference elements kept but flagged `peripheral`. Downstream
components (fingerprints, verifier, benchmark) consume the core graph by
default. Extraction uncertainty is thereby represented *structurally*
(core/peripheral) rather than as uncalibrated LLM confidence floats. Manually
authored Thought Graphs bypass stages 1–3 and enter at validation, making the
LLM optional by construction.

# Confidence

MEDIUM-HIGH for the contract shape (staging, spans, closed vocabularies,
validation are all standard hard-won lessons of semantic annotation), MEDIUM
for the exact taxonomy sizes. Main uncertainty (<100 words): whether two-pass
agreement retains *enough* graph — if the intersection is routinely below
~70% of triples, the core is too sparse to fingerprint and the schema must be
simplified further. This number is measurable in the toy experiment and must
gate everything downstream. The human ceiling is known: AMR expert
inter-annotator Smatch ≈ 0.83–0.89 on the same sentence under a mature frozen
schema — v0.1 should not expect to beat it.

# Best Algorithm / Method

Not an algorithm but a **contract**: staged LLM extraction into a validated
JSON schema.

Node taxonomy v0.1 — six types (deliberately smaller than the README's ten;
every additional type is measured annotator disagreement): `entity`,
`state`, `event`, `goal`, `constraint`, `claim`. (README's evidence/method/
knowledge/outcome map to `claim`/`entity`/`state` + edge semantics; knowledge
anchoring is R0-E's field, not a node type.)

Edge taxonomy v0.1 — seven types, each with `polarity ∈ {+,−}`: `causes`
(−: prevents), `requires` (prerequisite/enabling), `supports` (evidence for;
−: contradicts), `part-of`, `precedes`, `about`, `motivates` (goal linkage).
Higher-order support: exactly one level — an edge may take another edge's id
as an argument (needed for cause-of-cause; see R0-A2), extracted in a
dedicated sub-stage that runs *after* first-order edges exist.

Record format (extraction contract, abbreviated):

```json
{
  "thought_id": "t-…",
  "extractor": {"model": "…", "version": "…", "prompt_hash": "…", "passes": 2},
  "nodes": [{"id":"n1","type":"state","label":"heat accumulation",
              "spans":[[128,148]],"status":"core"}],
  "edges": [{"id":"e1","type":"causes","polarity":"+",
              "args":["n0","n1"],"spans":[[110,160]],"status":"core"},
             {"id":"e7","type":"causes","polarity":"+",
              "args":["e1","n4"],"spans":[[161,190]],"status":"peripheral"}]
}
```

# Answers to the mission's Resolve questions

1. **Reliably extractable:** proposition boundaries; nodes at the 6-type
   grain; first-order typed edges with polarity when the text states them
   explicitly; source spans. Moderately reliable: implicit causal links,
   `motivates`, one-level higher-order edges. 
2. **Too unstable for v0.1:** fine relation subtypes (correlates/contributes/
   triggers…), quantifiers and scope, temporal ordering beyond explicit
   `precedes`, cross-thought coreference, LLM-self-reported numeric
   confidence, nested higher-order beyond one level, node *importance*
   weights.
3. **Node taxonomy:** the six above. Fewer types = higher agreement = larger
   core graph; nuance belongs to edges and labels.
4. **Edge taxonomy:** the seven above.
5. **Keep distinct or merge?** Keep `causes`, `requires`, `supports`
   distinct — the verifier's seed generation (R0-A2) needs relational
   identity, and these three are the analogy-bearing types. Fold exotic
   subtypes into them rather than growing the vocabulary. `contradicts` is
   `supports` with negative polarity, not a separate type.
6. **Uncertainty representation:** `status: core|peripheral` from two-pass
   agreement + `passes` metadata. Structural, reproducible, no floats.
7. **Provenance:** `spans` (char offsets into the stored source context) are
   mandatory on every node and edge; validation rejects any element without
   at least one span. This is simultaneously the hallucination defence and
   the audit trail for explanations.
8. **Approximate canonicality:** closed vocabularies + lemmatized lowercase
   labels + deterministic serialization (topological order, ties
   alphabetical) + agreement-core. Canonicality is *approached*, never
   achieved — downstream layers must tolerate residual variance (this is the
   central constraint R0-H2 places on fingerprinting).
9. **Hallucination prevention/measurement:** prevention — span mandate +
   extraction prompt forbids inferred edges (only stated or strongly implied
   with the implying span). Measurement — (a) span-coverage rate is
   automatically 100% by validation, so audit *span faithfulness*: sample
   edges, check the span actually asserts the relation (human or judge-LLM
   spot check, off the critical path); (b) two-pass disagreement rate as a
   continuous canary; (c) benchmark track for fabricated-relation rate on
   texts with known gold graphs.
10. **One-pass vs staged:** staged, unambiguously. Each stage is separately
    schema-validated, separately debuggable, separately regression-tested;
    failures localize. One-pass free-form JSON is where reification drift
    and hallucinated structure breed.
11. **Manual authoring path:** humans (or non-LLM tools) write the same JSON;
    `extractor.model = "human"`; validation and canonicalization identical.
    The comparison engine cannot tell the difference — which is the proof
    that the LLM is genuinely at the boundary.

# Example Thought Graphs (required artifact)

Two deliberately analogous cross-domain examples in the proposed contract
(spans reference the stored source texts; `p` = polarity):

```json
{"thought_id":"ex-battery",
 "extractor":{"model":"human","version":"dna-0.1","passes":1},
 "nodes":[
  {"id":"n0","type":"entity","label":"battery pack","spans":[[0,11]],"status":"core"},
  {"id":"n1","type":"state","label":"heat accumulation","spans":[[25,58]],"status":"core"},
  {"id":"n2","type":"state","label":"electrode degradation","spans":[[60,102]],"status":"core"},
  {"id":"n3","type":"event","label":"cell failure","spans":[[104,131]],"status":"core"},
  {"id":"n4","type":"constraint","label":"passive cooling only","spans":[[133,170]],"status":"core"}],
 "edges":[
  {"id":"e1","type":"causes","p":"+","args":["n0","n1"],"spans":[[12,58]],"status":"core"},
  {"id":"e2","type":"causes","p":"+","args":["n1","n2"],"spans":[[60,102]],"status":"core"},
  {"id":"e3","type":"causes","p":"+","args":["n2","n3"],"spans":[[104,131]],"status":"core"},
  {"id":"e4","type":"requires","p":"-","args":["n4","n1"],"spans":[[133,170]],"status":"peripheral"},
  {"id":"e5","type":"causes","p":"+","args":["e1","n3"],"spans":[[104,131]],"status":"peripheral"}]}
```

```json
{"thought_id":"ex-organization",
 "extractor":{"model":"human","version":"dna-0.1","passes":1},
 "nodes":[
  {"id":"n0","type":"entity","label":"fast-growing team","spans":[[0,17]],"status":"core"},
  {"id":"n1","type":"state","label":"unprocessed information accumulation","spans":[[19,73]],"status":"core"},
  {"id":"n2","type":"state","label":"coordination degradation","spans":[[75,120]],"status":"core"},
  {"id":"n3","type":"event","label":"organizational collapse","spans":[[122,158]],"status":"core"},
  {"id":"n4","type":"goal","label":"keep shipping weekly","spans":[[160,193]],"status":"core"}],
 "edges":[
  {"id":"e1","type":"causes","p":"+","args":["n0","n1"],"spans":[[18,73]],"status":"core"},
  {"id":"e2","type":"causes","p":"+","args":["n1","n2"],"spans":[[75,120]],"status":"core"},
  {"id":"e3","type":"causes","p":"+","args":["n2","n3"],"spans":[[122,158]],"status":"core"},
  {"id":"e4","type":"motivates","p":"+","args":["n4","n0"],"spans":[[160,193]],"status":"peripheral"}]}
```

The shared core skeleton (entity →causes→ state →causes→ state →causes→
event) is what the delexicalized channels must expose; the differing
peripheral edges (`requires` constraint vs `motivates` goal) are honest
divergence, not noise. A third example with a negative-polarity edge
("audits prevent fraud") lives in the toy-experiment inputs.

# Required Thought DNA (what extraction can actually supply)

Reliable now: node `type` (6-way), `label`, `spans`; edge `type` (7-way),
`polarity`, ordered `args`, `spans`; `status` core/peripheral; extractor
metadata (model, version, prompt hash) — mandatory for index scoping.
Plausible soon: one-level higher-order edges (moderate reliability — measure
before trusting); `modality` (factual/hypothetical/desired) — extractable but
unvalidated, ship as optional field, do not let the verifier depend on it
until measured. Not supplied: quantifiers, importance, calibrated confidence.

# Required Graph Representation

Directed typed multigraph with one-level edge reification (edge-as-argument),
exactly as R0-A2 requires — the extraction layer can supply it; deeper
nesting it cannot reliably supply, which conveniently matches what the
verifier actually consumes.

# Invariances

Extraction is where invariances are *created or destroyed*, not supported:

| Transformation | Effect at extraction |
|---|---|
| A paraphrase | main threat: decomposition drift; mitigated by small taxonomies + agreement core |
| B vocabulary | labels differ, types/edges should not — measurable |
| C ordering | canonical serialization removes it |
| D irrelevant branches | extraction faithfully adds them; downstream must ignore (do not filter at extraction — "irrelevant" is not extraction's judgment) |
| E partial | inherent |
| F granularity | second-worst threat (chain vs collapsed edge); R0-D's contraction operates on extraction output; extraction should not guess |
| I extraction mistakes | the object itself; two-pass core is the mitigation |

# Retrieval vs Verification

Neither — this is the **front end**. But it owns the system's noise floor:
per R0-H2, if extraction self-consistency (same text, two runs) is below
~0.85 Smatch, fingerprint-primary retrieval is dead on arrival regardless of
index design, and even verifier scores blur. The extraction contract
therefore ships with a mandatory **self-consistency CI gate**.

# Computational Cost

Per thought: 4–6 LLM calls ×2 passes (segmentation may batch) — seconds and
fractions of a cent-equivalent per thought; corpus-scale re-extraction on
extractor upgrade is the dominant lifecycle cost (1M thoughts × 2 passes —
budget explicitly; this is an argument for freezing extractor versions per
index epoch). Validation/canonicalization: microseconds, pure Python.

# Existing Implementations

- JSON-schema validation: `jsonschema` (mature).
- Smatch scoring: the reference `smatch` package (mature, small).
- AMR parsers (amrlib etc.) exist but target AMR, not Thought DNA; useful as
  design reference only — do not adopt AMR as the schema (it lacks polarity
  prominence, its concept grain is wrong for thoughts, and its own expert
  IAA ceiling of 0.83–0.89 warns against schema complexity).
- Structured-output constrained decoding (JSON mode) in any modern LLM API:
  use it; it eliminates malformed-output failure class entirely.

# Minimal Pseudocode

```
def extract(text):
    props  = llm_segment(text)                        # stage 1
    def one_pass():
        nodes = llm_nodes(props, NODE_TYPES)          # stage 2, spans required
        edges = llm_edges(props, nodes, EDGE_TYPES)   # stage 3a, first-order
        hos   = llm_higher_order(edges)               # stage 3b, one level
        return validate(canon(nodes, edges + hos))    # stages 4-5, reject uncited
    g1, g2 = one_pass(), one_pass()                   # stage 6
    core   = intersect(g1, g2)                        # label-lemma + type + args match
    return mark(core, "core") | mark(sym_diff(g1,g2), "peripheral")
```

# Toy Experiment

≤2h. 20 texts (4–8 sentences, mixed domains, incl. 5 with explicit
cause-of-cause statements). Run the full contract; measure: (i)
**self-consistency** — Smatch(g1, g2) per text; (ii) **core retention** —
|core| / |g1 ∪ g2|; (iii) **higher-order recovery** — fraction of the 5
planted cause-of-cause structures present in core. Decision rules: median
self-consistency < 0.75 → simplify schema (drop a node type or edge type,
rerun); core retention < 0.6 → same; higher-order recovery < 0.5 → verifier
must not rely on systematicity weights yet (degrade λ→1, revisit). This
experiment is the falsifier for this report *and* the calibration input for
R0-A2 and R0-H2's self-retrieval gate.

# Failure Modes

1. **Reification drift** — same relation as edge vs mechanism-node across
   passes; mitigations: edges-first contract, mechanism nodes only when the
   text names one, agreement core absorbs the residue.
2. **Granularity drift** — one pass compresses a stated chain; core loses
   the chain (intersection takes the sparser reading). Acceptable for v0.1;
   R0-D handles cross-thought granularity.
3. **Span laundering** — model cites a real span that does not assert the
   edge; only spot audits catch it (benchmark track 9/12 in R0-G).
4. **Boilerplate inflation** on verbose texts — faithful but noisy; handled
   downstream (IDF, unmatched-structure tolerance), not by extraction.
5. **Coreference splits** — "the company"/"the org" become two nodes;
   lemma-level label merge catches some; accept the rest v0.1.
6. **Version drift** — silent extractor upgrade invalidates comparability;
   extractor metadata + index scoping is mandatory, not optional.

# What NOT To Build

Open relation vocabulary (OpenIE-style free predicates — kills relational
identity, hence kills the verifier); one-pass "extract a graph" prompting;
LLM-reported confidence floats; full coreference resolution; automatic
irrelevance filtering at extraction; AMR adoption wholesale; extraction-time
canonical *concept* linking (that is R0-E's layer, optional).

# Architecture Consequences

- The 6-node/7-edge closed vocabularies above are the concrete v0.1 schema
  proposal; freeze after the toy experiment, version explicitly (`dna-0.1`).
- `status: core|peripheral` becomes a first-class Thought DNA field; all
  matching components default to core-only.
- Extractor identity (model/version/prompt-hash) scopes every index; plan
  re-extraction as a budgeted lifecycle event.
- Self-consistency Smatch is a CI gate in front of all retrieval/verifier
  work — the single cheapest system-level safety check.
- Higher-order recovery rate decides whether systematicity scoring (R0-A2)
  activates in v0.1.
- Manual-authoring path guarantees the LLM stays at the boundary; keep the
  human-JSON path tested in CI so it cannot rot.

# Sources

1. Banarescu et al. — *Abstract Meaning Representation for Sembanking*, LAW
   2013 (+ subsequent AMR IAA studies, expert same-sentence Smatch ≈
   0.83–0.89; 0.79 for webtext in Banarescu et al.). The empirical ceiling
   that sizes every
   reliability claim here.
2. Cai, Knight — *Smatch*, ACL 2013. The agreement metric used for the core
   gate and toy experiment.
3. Chalmers, French, Hofstadter — *High-Level Perception…*, JETAI 1992.
   Representation-building does the real work; staged contracts and spans
   are the discipline that keeps it inspectable.
4. Forbus, Oblinger — *Making SME Greedy and Pragmatic*, 1990 (with
   Falkenhainer et al. 1989). Defines what the downstream verifier needs
   extraction to preserve (typed relations, roles, one-level nesting).
5. Wang — *An Industrial-Strength Audio Search Algorithm*, ISMIR 2003. Via
   R0-H2: the reproducibility standard a fingerprintable front end would
   need — used here as the argument for the self-consistency gate.
