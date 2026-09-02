---
mission: R0-E
run: E2 (independent repeat, REPEAT_CLAIM)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  The canonical R0-E submission (PR #23) was NOT read. Unavoidable exposure:
  its issue/PR title ("Knowledge DNA v0.1 dual-field concept-ID interface"),
  seen during board-state determination. The title reveals the canonical
  design's gist (two fields, concept IDs) — and since the mission itself
  asks to distinguish "about" from "required" knowledge, some two-field
  convergence is forced by the mission text; still, do not score interface-
  shape convergence as independent. Scoring-mechanism and verdict
  convergence/divergence may be scored. Same-agent note: one of eight
  sequential runs by one agent in one session; this run consciously carries
  over R0-H2's argument that knowledge overlap is anti-correlated with
  cross-domain analogy.
---

# Decision

Split verdict, and the split is the point. **As an independent resonance
signal: NO** — knowledge overlap is largely redundant with semantic
similarity within a domain and is *anti-correlated* with the flagship
cross-domain analogy case (a battery engineer and an organizational theorist
with isomorphic failure structures share almost no required knowledge);
folded into the resonance score it actively suppresses the matches Resonance
exists to find. **As infrastructure: YES, twice** — (1) concept anchoring
gives the semantic channel a vocabulary-independent node affinity signal
(cheap, useful for B-invariance), and (2) required-knowledge sets power
**complementary resonance** ("whose knowledge begins where mine ends"),
which no other component addresses. Knowledge DNA v0.1 should therefore be
a minimal, optional, two-field node annotation — `about` (concept IDs) and
`requires` (concept IDs) — anchored to Wikidata QIDs with a free-text
fallback, scored only inside (a) node affinity for alignment seeds and
(b) the complementarity detector. It must be excluded from S_rel and from
any aggregate resonance scalar in v0.1, and it is explicitly **optional for
the first benchmark** (R0-G runs entirely without it).

# Confidence

HIGH on the exclusion-from-resonance-score decision (it follows from the
project's own flagship example; the argument is structural, not empirical).
MEDIUM on Wikidata as the anchor space. Main uncertainty (<100 words):
linking quality on abstract thought-node labels ("coordination degradation")
— entity linkers are tuned for named entities, not abstract concepts;
coverage may be poor and noisy. That is why every scoring path treats
missing/failed anchors as "no evidence" rather than "no match", and why
free-text fallback is mandatory.

# Answers to the mission's Resolve questions

1. **What a node points to:** `about: [concept-id…]` — what the node is
   about (≤3 per node); optionally `requires: [concept-id…]` — knowledge
   needed to understand/solve it (mostly attached at thought level or to
   goal/constraint/claim nodes; per-node everywhere is over-annotation).
   Concept-id = Wikidata QID when the linker is confident; otherwise a
   normalized free-text term marked `unanchored`.
2. **"About" vs "required" must not be conflated** — they behave oppositely
   under the project's core use cases: cross-domain analogues *differ* in
   both, same-domain colleagues *share* both, and complementary partners
   share `about` while differing in `requires` (that difference is the
   signal). One field cannot encode this.
3. **Scoring overlap/proximity:** weighted Jaccard over concept sets for
   overlap; proximity for non-identical concepts via (a) shared ancestors in
   the Wikidata subclass/part-of hierarchy (≤2 hops) at half weight, else
   (b) cosine of concept-label embeddings at quarter weight. Deliberately
   crude — this is a tiebreaker and a complementarity feature, not a
   resonance verdict, and crude+inspectable beats learned+opaque here.
4. **Nearby-but-not-identical concepts:** as in 3; never chase multi-hop
   graph walks in v0.1 (2 hops max — beyond that Wikidata's ontology mixes
   granularities unpredictably and "proximity" becomes noise).
5. **Books/papers/courses/patents/datasets/tools/experts:** resources hang
   *off concepts*, not off thoughts: `resource → teaches/covers →
   concept-id`. Nothing in matching touches resources; they are a later
   presentation-layer join ("to continue this branch you may need X; here
   are entry points"). Keeping the primary object the concept, not the
   resource list, is what the master brief already says — v0.1 should hold
   that line and build no ingestion pipeline.
6. **Cross-domain vs same-domain:** knowledge structure mostly helps
   same-domain matching (where it is redundant) and complementarity (where
   it is unique). For cross-domain analogy it is negative evidence and must
   be kept out — the central finding of this run, argued in full in R0-H2's
   attack 10.
7. **Implementable without a universal ontology:** exactly the above —
   off-the-shelf linking (spaCy entity-linker/OpenTapioca-class tools, or
   LLM-proposed QIDs validated against the Wikidata API at extraction
   time), free-text fallback, no local ontology copy beyond a cached
   ancestor lookup, no ingestion. OpenAlex note: its `concepts` scheme is
   deprecated/frozen (replaced by curated `topics`); do not anchor to
   OpenAlex concepts; its topics tree is usable later for scholarly-domain
   tagging only.
8. **The tiny interface Thought DNA exposes now (Knowledge DNA v0.1):**

```json
{
  "id": "n7",
  "type": "state",
  "label": "coordination degradation",
  "knowledge": {
    "about":    [{"id": "Q1783823", "label": "coordination", "conf": "linked"},
                 {"label": "organizational degradation", "conf": "unanchored"}],
    "requires": [{"id": "Q149584", "label": "organizational theory", "conf": "linked"}]
  }
}
```

   The `knowledge` object is optional everywhere; absence means "not
   annotated", and no scorer may interpret absence as dissimilarity. That
   single rule is what lets a richer knowledge graph be added later without
   re-extracting anything.

# Required Thought DNA

Only the optional `knowledge` object above + linker version metadata.
No new mandatory fields — deliberately: mandatory knowledge annotation
would gate the whole pipeline on the weakest, least-validated component.

# Required Graph Representation

Unchanged. Concept space is an external coordinate system referenced by ID,
never materialized into the Thought Graph as nodes (mixing knowledge nodes
into the thought topology would corrupt structural fingerprints and
alignment — the graph would grow edges that the thinker never thought).

# Invariances

Knowledge anchoring *contributes* one invariance rather than consuming the
table: B (vocabulary substitution) — "лебедь"/"swan"/"cygnus" link to one
QID, giving alignment seeds a vocabulary-free affinity signal. It does
nothing for structural invariances and must not pretend to.

# Retrieval vs Verification

Neither, in v0.1. Explicitly kept out of retrieval (a knowledge-overlap
index would pull same-field colleagues — the "similar profile" failure mode
the README rejects on page one). Used in: (a) verification seed affinity
(small additive term next to label-embedding cosine); (b) the
complementarity detector, which runs *after* verification on aligned pairs:
`complementarity = overlap(about) · (1 − overlap(requires)) · residue_mass`
— same subject, disjoint know-how, and one graph continues past the other.

# Computational Cost

Linking: one call per node label at extraction time (cached by lemma);
negligible vs LLM extraction itself. Scoring: set operations over ≤3-element
sets — microseconds. Ancestor cache: a few MB. Corpus scale: no index, no
problem.

# Existing Implementations

- Wikidata API + SPARQL endpoint (mature, rate-limited — cache).
- spaCy-entity-linker / OpenTapioca-class Wikidata linkers (community
  maturity moderate; fine for optional annotation with confidence gating).
- BLINK/REL-class neural linkers (mature research code, Wikipedia-target,
  heavier; overkill v0.1).
- LLM-proposed QID + API validation is the pragmatic v0.1 route: the
  extractor already reads the label in context; validation kills
  hallucinated IDs. Dependency risk: Wikidata availability — cache
  aggressively, degrade to unanchored gracefully.

# Minimal Pseudocode

```
def knowledge_affinity(a, b):                 # seed-affinity term ∈ [0,1]
    A, B = anchors(a), anchors(b)             # 'about' concept sets
    if not A or not B: return None            # absence ≠ dissimilarity
    return (w_jaccard(A, B)
            + 0.5 * ancestor_overlap(A, B, hops=2)
            + 0.25 * emb_cos_bestpair(A, B))  # clipped to 1

def complementarity(pair):                    # after verification
    s = overlap(pair.t1.about_all, pair.t2.about_all)
    d = 1 - overlap(pair.t1.requires_all, pair.t2.requires_all)
    return s * d * residue_mass(pair)
```

# Toy Experiment

≤2h. 30 node labels in 10 triples: (same concept, different vocabulary),
(nearby concepts), (unrelated). Link with the v0.1 route; measure: linking
coverage (fraction anchored), pair-affinity separation across the three
classes, and — the decisive test — run the 10 cross-domain analogy pairs
from R0-G's gold set through `knowledge_affinity`: **expected result ≈ 0**
(disjoint knowledge). If instead cross-domain analogues show high knowledge
affinity, this report's exclusion argument is falsified and Knowledge DNA
deserves promotion into the resonance score; if coverage < 50%, even the
seed-affinity use is premature — ship the interface, defer the scoring.

# Failure Modes

1. Linker anchors abstract labels to wrong-sense QIDs ("execution" the
   killing vs the running of plans) → poisoned affinity; confidence gate +
   unanchored fallback.
2. Absence-as-dissimilarity bug in some future scorer silently punishes
   unannotated thoughts — the "no evidence" rule must be enforced in the
   result schema (nullable term), not in reviewer memory.
3. Knowledge affinity leaks into ranking via the seed-affinity term more
   than intended → cross-domain recall drops; ablate in benchmark.
4. Wikidata hierarchy quirks make 2-hop ancestors connect absurd pairs
   (classic ontology hazards) → cap hop weight, whitelist relation types
   (subclass-of, part-of only).
5. Requires-annotation is the least reliable extraction output (the model
   guesses curricula) → thought-level requires only, marked low-confidence,
   excluded from any score until measured.
6. Resource attachment scope-creeps into an ingestion pipeline — the
   mission's own trap; v0.1 ships zero resource features.

# What NOT To Build

A universal ontology or local Wikidata mirror; knowledge-overlap retrieval
index; embedding-trained concept space (no-training rule); OpenAlex
concepts anchoring (deprecated); mandatory annotation; multi-hop ontology
path-finding; any resource ingestion.

# Architecture Consequences

- Knowledge DNA v0.1 = the optional two-field `knowledge` object above;
  schema it now, annotate opportunistically, require it nowhere.
- Hard rule into the scoring spec: knowledge terms appear only in seed
  affinity (nullable) and complementarity; never in S_rel, never in the
  ranking scalar, until the toy experiment's falsifier says otherwise.
- Complementarity detector = about-overlap × requires-disjointness ×
  residue mass; residues come free from the verifier (R0-C4).
- Linker identity/version joins extractor metadata in index scoping.
- R0-G runs without knowledge annotations; a knowledge-ablation track is
  added only after coverage ≥ 50% on real data.
- Resources remain presentation-layer, keyed by concept-id — no pipeline.

# Sources

1. Wikidata (entity schema, subclass/part-of hierarchy, public API/SPARQL).
   The anchor space and its known granularity hazards.
2. OpenAlex documentation — Concepts (deprecated, frozen) vs curated Topics
   hierarchy. Verified this run; grounds the "do not anchor to OpenAlex
   concepts" instruction.
3. spaCy-entity-linker / OpenTapioca (spaCy Universe), REL (Radboud), BLINK
   (Facebook Research). The practical linking-tool landscape and maturity
   assessment.
4. Forbus, Gentner, Law — MAC/FAC, 1995. Content-vector retrieval pulls
   surface-similar items — the cautionary precedent for why a knowledge-
   overlap retrieval channel reproduces "similar profile" matching.
5. Gentner 1983 (SMT). Analogy lives in relational structure, not shared
   domain knowledge — the theoretical basis for excluding knowledge overlap
   from analogical resonance.
