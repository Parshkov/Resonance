---
mission: R0-F
run: R0-F
contributor: Parshkov
agent_or_model: xAI Grok 4.6 (Grok Build TUI; more specific mode label not exposed)
date: 2026-08-31
mission_modified: false
web_research_used: true
blind_constraints_preserved: not-applicable
blind_sibling_exposure: none
agent_id: parshkov-xai-grok46-k3e8
tools_used:
  - web research of primary IE/discourse/KG-extraction papers
  - local Python span-IoU alignment check on two synthetic extracts of one paragraph
notes: >
  Same agent_id authored R0-E (PR #23) and R0-H (PR #29). This run did not open
  other agents' submissions. Extraction recommendations are from IE evidence,
  not from treating E/H as accepted DNA.
---

# Decision

**GO**, with a hard split: the extractor may be an LLM; the graph it emits must be a **span-grounded, closed-schema, staged** artifact that a non-LLM matcher can consume without calling a model again. v0.1 extracts (1) text spans as nodes, (2) a small role set, (3) a small directed relation set *only between already-extracted nodes*. Every node and edge keeps character-offset provenance and a confidence. Repeated extraction is canonicalized by span overlap, not by label strings. Nested SME-style `CAUSE[R1,R2]`, implicit causation, goal-vs-problem, and open relation phrases are **not** trusted at ingest. A human-authored graph uses the same JSON and sets `extractor: null`.

# Confidence

**HIGH** that unconstrained one-shot JSON dumps are the wrong contract (ACE relation IAA ~55% F1; LLM KG runs vary especially on relations; ungrounded triples are undetectable hallucinations). **MEDIUM** on the exact v0.1 inventories: they are the largest sets with an extractability argument, not a freeze of Thought DNA. Main uncertainty: implicit `causes` without a connective — frequent in thought, poorly agreed even by humans (PDTB implicit Cause is the majority of Cause tokens).

# Best Algorithm / Method

**Staged, schema-constrained, span-first extraction** (UIE-style schema instructor + AEVS-style anchors + DyGIE++-style “edges only on spans”).

```text
source text
  → 1. ANCHOR: enumerate mention spans (char offsets)
  → 2. TYPE: assign each span a closed node role or drop it
  → 3. LINK: score closed relations only on typed span pairs
  → 4. GROUND: reject any node/edge lacking a source span
  → 5. CUE-CHECK: drop polarity-sensitive rels with no lexical cue
  → 6. MERGE: coref-collapse spans with IoU ≥ τ (default 0.5)
  → 7. OPTIONAL: about/requires concept IDs with abstain
  → 8. VALIDATE: JSON Schema + dangling-edge check
```

**What is reliable enough to become structure**

| Field | Reliability | Why |
|---|---|---|
| mention span | high | ACE entity IAA ~86% F1 (Qi 2019, ACE’05 annotators) |
| `part_of` when explicit | high | preposition/possessive relations are the easy ACE class (Sun et al. 2012) |
| `causes` / `prevents` with cue (`because`, `leads to`, `prevents`) | medium-high | PDTB explicit class agreement ~94%; connectives mostly unambiguous (Pitler et al. 2008: 93% explicit) |
| node role (problem/state/outcome/method/…) | medium | coarse; confusable at boundaries |
| `requires` (need-to / before-can) | medium | often explicit (“need”, “requires”, “must know”) |
| `supports` / `contradicts` | medium-low | evidential vs causal mix-ups |
| implicit `causes` (no connective) | low | PDTB Cause implicitness 0.62–0.69; temporal/causal double-label on *when*/*since* (Webber et al. 2014) |
| goal vs problem | low | same span, different attitude |
| nested `CAUSE[R1,R2]` | low | not an IE span task; compile later from binary chains |
| open relation phrases | low | OpenIE synonym drift |

**Too unstable for v0.1 (do not emit, or emit only as `note`)**

- implicit causation without cue
- `precedes` vs `causes` (PDTB TEMPORAL/CONTINGENCY mix)
- `enables`, `motivates`, `seeks` as extra edge types
- `goal` as a distinct *edge*; if needed, use node role `outcome` on an explicit “want/need X”
- analogical `like` as a graph edge
- `is-a` / typing (that is optional Knowledge DNA, not thought structure)
- higher-order reified predicates at ingest

**Node taxonomy (extractable)**  
`problem | mechanism | state | outcome | constraint | method | evidence | resource | agent`

**Edge taxonomy (extractable, keep distinct)**  
`causes | prevents | requires | part_of | constrains | supports | contradicts`

Keep `prevents` separate from `causes`: polarity is a first-class hard negative for matching. Do **not** keep `goal` as an edge; `constraint` is a *node role* plus optional `constrains` edge. `supports`/`contradicts` stay distinct from `causes` (evidence vs mechanism) but carry lower default confidence.

**Uncertainty.** `extract_conf ∈ [0,1]` on every node and edge. Matcher treats missing/low-conf structure as unmatched, not as contradiction. Abstain (`conf < θ_drop`, default 0.35) deletes the object.

**Provenance.** Character offsets into the source string, plus the surface `text` slice. Edges should also record a `cue` span when the relation is lexically marked. AEVS (2026): if every triple element maps to a span, hallucinations become *detectable*.

**Canonical repeated extraction.** Align nodes by span IoU (not labels). Merge if IoU ≥ 0.5; optional same-role constraint. Self-match metric = aligned node/edge F1 across two extracts of one text. Label-string identity is not the metric.

**Hallucinations.** Prevent: (a) no edge unless both endpoints exist; (b) no object without a span; (c) closed relation enum; (d) cue-check for `prevents`/`contradicts`; (e) JSON Schema / constrained decoding. Measure: fraction of edges failing (b) or (d); self-match F1.

**One-pass vs staged.** Staged. One-shot “dump a thought graph” mixes span errors into invented relations (ACE: pipelined relation F1 already ~50%; human end-to-end relation F1 ~64–70%). UIE (Lu et al. 2022) still *conditions on a schema*. AEVS splits anchor discovery from grounded linking. Joint span models (DyGIE++, Wadden et al. 2019) share span representations but still enumerate spans first.

**Manual bypass.** Same JSON. `extractor: null`, `human_id` set. Spans recommended but not required for human graphs; matcher must accept span-less nodes so a researcher can type a graph. No LLM in that path.

# Why It Fits Resonance

The matching engine is forbidden to be an LLM judge. That only works if extraction emits *inspectable, reproducible structure* rather than a model-dependent cloud of labels. ACE and PDTB say relations, especially implicit and verbal ones, are the unstable half — so v0.1 must not ask the extractor to also invent nested analogical predicates. Span grounding is how we stop the graph from drifting away from the thought. Closed schemas are how two extracts of one paragraph can be compared at all.

This is also the Chalmers/French/Hofstadter point operationalized: SME assumed the representation. F’s job is to say what representation we can actually *build from language* in 40 hours.

# Required Thought DNA

Extraction-layer fields only. Not a global DNA freeze.

**Required for any extracted graph**

- `source.text`
- node: `id`, `role`, `label`, `spans[]` (`start`,`end`,`text`), `extract_conf`
- edge: `id`, `src`, `dst`, `rel` (enum above), `extract_conf`, `spans[]` or `cue`

**Optional**

- `polarity` on `causes`/`prevents` (redundant if `prevents` is a rel)
- `about` / `requires` concept IDs with `conf` (empty = abstain)
- `extractor.{id,version}`
- human graphs: empty `spans`

**Do not require at ingest:** WL colors, fingerprint hashes, GW costs, nested predicates, universal ontology IDs.

# Required Graph Representation

Directed typed property graph. Nodes are span-backed mentions (possibly merged). Edges are binary typed relations. Higher-order systematicity, if a verifier needs it, is **compiled** from `causes`/`requires` chains after ingest (`CAUSE(n1→n2, n2→n3)`), not extracted as a hyperedge. Not a tree. Not OpenIE triples with free-text predicates.

# Invariances

Extraction’s job is to *survive* some transformations and to *expose* others as graph differences.

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---|---|---|---|
| A paraphrase | | yes | | span alignment + roles; labels may differ |
| B vocabulary substitution | | yes | | same; optional concept IDs |
| C node ordering | yes | | | graph, not sequence |
| D irrelevant branches | | yes | | extra low-conf nodes; matcher may ignore |
| E partial observation | | yes | | missing nodes; no hallucinated fill |
| F granularity | | | as identity | two extracts may insert `X→Y` intermediaries; not a self-match failure if spans nest |
| G different graph sizes | | yes | | expected across extracts |
| H domain substitution | n/a at extract | | | extractor does not analogize |
| I modest extraction mistakes | | first-class | | `extract_conf`, cue-filter, self-match F1 |

# Retrieval vs Verification

Extraction is **upstream of both**. It must not be a third matching stage. Retrieval/verification read the JSON; they do not re-prompt an LLM on the pair of thoughts.

# Computational Cost

One thought (10–100 nodes): one LLM pass over ≤2k tokens plus O(n²) pair scoring. Seconds. Constrained JSON is cheaper than unconstrained repair. 1M thoughts is ingest cost only — never extract on the comparison path.

# Existing Implementations

| Piece | Artifact | Risk |
|---|---|---|
| Schema-conditioned generation | UIE (Lu et al. 2022; `universal-ie/UIE`) | Research code; idea (SSI) is what we copy |
| Span IE | DyGIE++ (`dwadden/dygiepp`) | ACE/SciERC trained; schema is not Thought roles — do not drop in |
| Grounded LLM triples | AEVS (Computers 2026, 15(3):178) | Anchor-then-link; copy the provenance constraint |
| Constrained JSON | `outlines` / JSON Schema | Still validate spans after parse |
| OpenIE | Stanford OpenIE, ClausIE | Reject: uncanonical predicates |
| Validation | JSON Schema + SHACL-like checks (Uwasomba 2026) | Determinism is in the harness |

# Minimal Pseudocode

```text
extract(text, schema):
  spans = llm_anchors(text)                 # char offsets only
  nodes = []
  for s in spans:
    r, c = llm_role(s, schema.roles)
    if c >= θ_drop: nodes.append(Node(s, r, c))
  nodes = merge_iou(nodes, τ=0.5)
  edges = []
  for a,b in pairs(nodes):                  # same-sentence first
    rel, c = llm_rel(a, b, schema.rels)
    if c < θ_drop: continue
    if rel in {prevents, contradicts} and not cue(text, rel): continue
    if not grounded(a) or not grounded(b): continue
    edges.append(Edge(a,b,rel,c))
  validate_schema(nodes, edges)
  return Graph(text, nodes, edges, extractor=id)

# human bypass
ingest_manual(json): validate_schema(json); json.extractor = null
```

# Toy Experiment

**Falsify:** “two extracts of one paragraph are the same graph if we compare node labels.”

**Text.**  
`Lithium-ion batteries accumulate heat during fast charging. The heat causes SEI growth and capacity fade, which leads to cell failure.`

**Extract A (5 nodes, 5 `causes`).** Labels: Li-ion battery, heat accumulation, SEI growth, capacity fade, cell failure.

**Extract B (typical LLM drift).** Relabeled (lithium ion cell / heat / fade / failure of the cell), dropped SEI, added `fast charging`, hallucinated `heat -prevents-> failure`.

**Local Python, span IoU ≥ 0.3:**

| Metric | Value |
|---|---|
| label-string Jaccard | **0.00** |
| span-aligned node recall / prec | **0.60 / 0.60** |
| aligned edge precision | 0.20 (hallucinated `prevents` + extra edges) |
| `prevents` after cue-filter | **dropped** (no prevent/avoid/inhibit in text) |

**Expected if the contract is right:** label identity fails; span alignment recovers the shared mentions; cue-filter removes the polarity hallucination.

**Metric:** self-match must be span-aligned F1, not exact JSON. A v0.1 extractor **fails** if two greedy extracts of this paragraph have span-aligned node F1 < 0.5 after merge.

# Failure Modes

1. **Ungrounded node.** LLM emits `thermal runaway` not in the text. Span check drops it.
2. **Hallucinated polarity.** `heat prevents failure` on a “causes fade” paragraph. Cue-filter drops `prevents`.
3. **Implicit cause invented.** Adjacent sentences, no connective, model adds `causes`. v0.1: only emit `causes` if cue *or* `conf` is separately calibrated; default drop implicit.
4. **Goal/problem flip.** “I need a SEI model” as `problem` vs `outcome`. Roles disagree; span still aligns. Matcher should not require role equality for node correspondence.
5. **Granularity split.** Extract A: `SEI→fade`. Extract B: `SEI→resistance→heat→fade`. Span nesting, not a fingerprint key.
6. **OpenIE synonym.** `leads_to` vs `causes` vs `results_in` as three rels. Closed enum prevents this.
7. **Knowledge-ID leak.** Linking `bank` in “river bank” to finance. Optional IDs must abstain; they are not extraction identity.
8. **Self-mismatch as matching failure.** Two extracts of one thought fail label-equality and get scored as non-resonant. That is an extractor bug, not a matcher bug — hence span canonicalization.

# What NOT To Build

- One-shot “write a Thought Graph in free JSON.”
- OpenIE / free-text predicates as v0.1 DNA.
- Nested SME predicates at ingest.
- Using an LLM to *compare* two graphs (violates the matching rule).
- Training a domain GNN extractor in the sprint (no labeled thought graphs).
- Treating extraction variance as analogical signal.
- Frozen maximal taxonomy (goal, hypothesis, enables, precedes, analogical-to, …) before self-match is measured.

# Architecture Consequences

1. Thought ingest = staged span→role→closed-rel pipeline with provenance.
2. Matcher input is this JSON; no LLM on the comparison path.
3. Self-match (span-aligned F1 of two extracts) is a gate before fingerprint/verifier research is believed.
4. `prevents` stays distinct from `causes`.
5. `requires` stays distinct from `causes` (prerequisite vs mechanism).
6. Higher-order relations are compiled post-ingest if a verifier needs systematicity.
7. Human graphs share the schema and skip stages 1–5.
8. Optional concept IDs attach here with abstain; they do not define the graph.
9. Benchmark G should include: two-extract self-match, polarity hallucination, implicit-cause bait, goal/problem role swap, nested-granularity pair.
10. Do not freeze DNA beyond this extraction contract until F’s self-match experiment is run for real.

# Sources

1. Qi, P. (2019). *Joint Mention and Relation Extraction.* Thesis table: ACE’05 entity IAA F1 86.5 vs relation IAA F1 55.0; human end-to-end relation F1 ~64–70. **Why:** relations, not mentions, are the unstable object.
2. Sun et al. (2012). *Why Review Two Versions of ACE?* Verbal/Other relations harder than Preposition/Possessive. **Why:** prefer explicit `part_of`; distrust verbal implicit links.
3. Prasad, Miltsakaki, Webber et al. PDTB 2.0 / Webber et al. 2014 *CL*. Class agreement ~94%; subtype ~80%; *when*/*since* temporal+causal mix; implicit Cause majority. **Why:** explicit `causes` only in v0.1; no `precedes`/`causes` merge.
4. Pitler, E., et al. (2008). Easily identifiable discourse relations. ~93% accuracy on *explicit* PDTB senses. **Why:** cue-check is high-value.
5. Lu, Y., et al. (2022). UIE. ACL. Schema instructor + text-to-structure. **Why:** closed schema in the prompt, not post-hoc cleanup.
6. Wadden, D., et al. (2019). DyGIE++. EMNLP. Span enumeration then relations/events. **Why:** edges on spans, not invented arguments.
7. Liu et al. / AEVS (2026). *Computers* 15(3):178. Anchor-constrained LLM triples with char provenance. **Why:** ungrounded = detectable hallucination.
8. Uwasomba, C., Nnamoko, N., & Korkontzelos, Y. (2026). ICCSC. Raw LLM KG extraction varies across runs; relations worse as temperature rises; SHACL/canonical IRIs restore determinism. **Why:** harness, not the model, is the contract.
9. Banko, M., & Etzioni, O. (2008). Open IE from the Web. **Why:** reject free predicates for a matcher that needs a closed rel set.
10. Chalmers, D., French, R., & Hofstadter, D. (1992). High-level perception. *JETAI*. **Why:** extraction *is* the analogical representation problem.

# Example Thought Graphs (JSON)

G1/G2 extracted-style; G3 manual bypass. Offsets are 0-based into `source.text`.

**G1 — battery (extracted)**

```json
{
  "thought_id": "ex-battery-fade",
  "source": {"text": "Lithium-ion batteries accumulate heat during fast charging. The heat causes SEI growth and capacity fade, which leads to cell failure."},
  "extractor": {"id": "contract-example", "version": "r0f-v0.1"},
  "nodes": [
    {"id": "n1", "label": "lithium-ion batteries", "role": "resource", "spans": [{"start": 0, "end": 21, "text": "Lithium-ion batteries"}], "extract_conf": 0.93},
    {"id": "n2", "label": "heat", "role": "state", "spans": [{"start": 33, "end": 37, "text": "heat"}], "extract_conf": 0.91},
    {"id": "n3", "label": "SEI growth", "role": "mechanism", "spans": [{"start": 76, "end": 86, "text": "SEI growth"}], "extract_conf": 0.88},
    {"id": "n4", "label": "capacity fade", "role": "state", "spans": [{"start": 91, "end": 104, "text": "capacity fade"}], "extract_conf": 0.90},
    {"id": "n5", "label": "cell failure", "role": "outcome", "spans": [{"start": 121, "end": 133, "text": "cell failure"}], "extract_conf": 0.92}
  ],
  "edges": [
    {"id": "e1", "src": "n1", "dst": "n2", "rel": "causes", "extract_conf": 0.72, "cue": {"start": 22, "end": 32, "text": "accumulate"}},
    {"id": "e2", "src": "n2", "dst": "n3", "rel": "causes", "extract_conf": 0.86, "cue": {"start": 69, "end": 75, "text": "causes"}},
    {"id": "e3", "src": "n2", "dst": "n4", "rel": "causes", "extract_conf": 0.84, "cue": {"start": 69, "end": 75, "text": "causes"}},
    {"id": "e4", "src": "n3", "dst": "n5", "rel": "causes", "extract_conf": 0.80, "cue": {"start": 112, "end": 117, "text": "leads"}},
    {"id": "e5", "src": "n4", "dst": "n5", "rel": "causes", "extract_conf": 0.80, "cue": {"start": 112, "end": 117, "text": "leads"}}
  ]
}
```

**G2 — organization (extracted; analog surface, same contract)**

```json
{
  "thought_id": "ex-org-coord",
  "source": {"text": "As an organization accumulates information without a shared model, coordination degrades and the project fails."},
  "extractor": {"id": "contract-example", "version": "r0f-v0.1"},
  "nodes": [
    {"id": "n1", "label": "organization", "role": "resource", "spans": [{"start": 6, "end": 18, "text": "organization"}], "extract_conf": 0.92},
    {"id": "n2", "label": "information", "role": "state", "spans": [{"start": 31, "end": 42, "text": "information"}], "extract_conf": 0.90},
    {"id": "n3", "label": "shared model", "role": "constraint", "spans": [{"start": 53, "end": 65, "text": "shared model"}], "extract_conf": 0.78},
    {"id": "n4", "label": "coordination degrades", "role": "state", "spans": [{"start": 67, "end": 88, "text": "coordination degrades"}], "extract_conf": 0.86},
    {"id": "n5", "label": "project fails", "role": "outcome", "spans": [{"start": 97, "end": 110, "text": "project fails"}], "extract_conf": 0.88}
  ],
  "edges": [
    {"id": "e1", "src": "n1", "dst": "n2", "rel": "causes", "extract_conf": 0.70, "cue": {"start": 19, "end": 30, "text": "accumulates"}},
    {"id": "e2", "src": "n3", "dst": "n4", "rel": "constrains", "extract_conf": 0.61, "cue": {"start": 43, "end": 50, "text": "without"}},
    {"id": "e3", "src": "n2", "dst": "n4", "rel": "causes", "extract_conf": 0.68},
    {"id": "e4", "src": "n4", "dst": "n5", "rel": "causes", "extract_conf": 0.74}
  ]
}
```

**G3 — complementary method (manual bypass)**

```json
{
  "thought_id": "ex-sei-model-need",
  "source": {"text": "We need a quantitative model of SEI growth to predict capacity fade."},
  "extractor": null,
  "human_id": "Parshkov",
  "nodes": [
    {"id": "n1", "label": "SEI growth", "role": "mechanism", "spans": [{"start": 32, "end": 42, "text": "SEI growth"}], "extract_conf": 1.0},
    {"id": "n2", "label": "quantitative model", "role": "method", "spans": [{"start": 10, "end": 28, "text": "quantitative model"}], "extract_conf": 1.0},
    {"id": "n3", "label": "capacity fade", "role": "outcome", "spans": [{"start": 54, "end": 67, "text": "capacity fade"}], "extract_conf": 1.0}
  ],
  "edges": [
    {"id": "e1", "src": "n1", "dst": "n2", "rel": "requires", "extract_conf": 1.0, "cue": {"start": 3, "end": 7, "text": "need"}},
    {"id": "e2", "src": "n2", "dst": "n3", "rel": "causes", "extract_conf": 0.9, "cue": {"start": 46, "end": 53, "text": "predict"}}
  ]
}
```

G3’s `requires` is the complementary hook: another thought *about* a phase-field interface model should match `n2` on knowledge/`about`, not on isomorphic causation. Extraction must keep `requires` ≠ `causes` or that hook collapses.
