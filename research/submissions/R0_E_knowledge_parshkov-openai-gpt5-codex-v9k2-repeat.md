---
mission: R0-E
run: R0-E-REPEAT-V9K2
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-v9k2
agent_or_model: GPT-5-based Codex (exact deployed model/version not exposed)
runtime: codex
date: 2026-09-01
mission_modified: false
web_research_used: true
code_execution_used: true
additional_agents_used: false
blind_group: null
sibling_submission_read: false
---

### Decision

**Qualified GO.** External knowledge requirements can add an independent,
explainable signal, but Knowledge DNA v0.1 should be only a small optional
annotation on Thought nodes: separate namespaced concept references for what a
node is **about** and what knowledge it **requires**. Score three channels
separately: `about↔about` (same-domain evidence), `requires↔requires` (shared
prerequisites), and directional `requires(query)→about(candidate)` (potential
complementarity). Missing or disjoint knowledge evidence must never veto a
structural analogy. Do not build a universal ontology, train knowledge-graph
embeddings, or call a live knowledge service in the matching path.

This recommendation is compatible with the accepted `thought-dna/0.1`
`node.knowledge.{about,requires}` shape inspected in the current repository; no
schema change is needed for the first benchmark. A later resolver manifest can
add versioned cross-scheme mappings without changing stored Thought DNA.

### Confidence

**MEDIUM.** Stable identifiers and role separation are well supported; the
uncertainty is whether automatic extraction can identify *required* knowledge
reliably enough to beat topic overlap. Public taxonomies primarily classify
aboutness, not prerequisites. The signal should remain optional and separately
reported until an independently annotated benchmark shows lift.

### Best Algorithm / Method

Use a snapshot-pinned concept resolver plus one-to-one soft set matching.

1. Resolve each `knowledgeRef.id` to a canonical namespaced ID. Exact ID or a
   reviewed SKOS `exactMatch` scores `1.0`; `closeMatch` may score `0.75`; one
   allowlisted direct broader/narrower edge may score at most `0.45`. Do not
   transitively compose `closeMatch` or arbitrary `related` edges. SKOS itself
   makes close mappings non-transitive.
2. Drop unresolved and corpus-generic hubs from scoring while retaining them in
   provenance. A resolver snapshot owns the allowlist, document frequency,
   source version, and hash.
3. For two reference sets of at most eight items, build pair weights
   `s(i,j) * sqrt(conf_i * conf_j)` and find a maximum-weight one-to-one
   bipartite matching `M`.
4. Return a confidence-weighted soft Dice score:

   `K(A,B) = 2 * sum((i,j) in M, weight(i,j)) / (sum(conf_A) + sum(conf_B))`.

   One-to-one matching prevents duplicate or very broad anchors from matching
   many items. Confidence is extraction/linking certainty, not importance.
5. Compute `K_about`, `K_requires`, `K_supply_qc`, and `K_supply_cq`
   independently. Return matched IDs, mapping relation, resolver hash, and
   evidence coverage with every score. `unknown` is distinct from numeric zero.

For verification, compute these channels on structurally aligned node pairs or
the aligned subgraphs, not on flattened whole-Thought bags. Otherwise the same
concept on unrelated branches creates false support.

Information-content measures are a later option once Resonance owns a stable
taxonomy snapshot and frequency corpus. Resnik showed why raw edge count is
unreliable: taxonomy edges cover non-uniform semantic distances. v0.1 should
therefore cap direct hierarchy evidence rather than pretend every hop is equal.

### Why It Fits Resonance

- Namespaced IDs are less sensitive to paraphrase than labels and remain
  inspectable.
- Role separation answers a question text similarity cannot: two branches can
  mention different topics yet need the same technique, or one branch can
  contain knowledge the other explicitly needs.
- The score yields concrete explanations (exact concept, reviewed crosswalk, or
  one-hop hierarchy evidence) rather than an opaque embedding distance.
- Keeping channels separate preserves the project's central cross-domain case:
  a battery and an organization may be structurally analogous while correctly
  having `K_requires=0`.
- Snapshot resolution makes results reproducible and avoids network availability
  or taxonomy drift during matching.

### Required Thought DNA

The smallest useful v0.1 interface is already expressible as:

```json
{
  "id": "n-method",
  "knowledge": {
    "about": [
      {"id": "local:state-estimation", "conf": 0.93, "via": "human"}
    ],
    "requires": [
      {"id": "local:bayesian-filtering", "conf": 0.81,
       "via": "extractor:cue-v0.1"}
    ]
  }
}
```

Semantics:

- `about`: the node denotes, explains, or applies the concept.
- `requires`: understanding, solving, or executing the node needs the concept;
  mere mention is insufficient.
- `id`: stable `scheme:concept` identifier (`wd`, current OpenAlex topic,
  `acmccs`, or a versioned `local` vocabulary).
- `conf`: confidence in the annotation/link, not relevance or expertise.
- `via`: compact annotation provenance. Human assertions must remain
  distinguishable from extractor output.

Labels are display-only. Resolver/crosswalk version and generic-anchor policy
belong in the scoring configuration hash, not repeated in each Thought. Books,
papers, courses, patents, datasets, and tools are resource records linked to
concepts; they are not concepts. Experts are consented agents associated with
evidence of capability, never knowledge identifiers.

### Required Graph Representation

Keep the Thought as a directed typed property graph. Knowledge references are
node annotations; the external knowledge space is a separate typed concept
graph or a tiny cached resolver. No hypergraph or reification is required for
v0.1. Cross-scheme mappings must retain edge type and provenance because
`exact`, `close`, `broader`, and `related` are not interchangeable.

### Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---:|---:|---:|---|
| A. paraphrase | yes | | | same resolved IDs |
| B. vocabulary substitution | yes | | | IDs/crosswalk, not labels |
| C. node ordering | yes | | | unordered reference sets |
| D. irrelevant branches | | yes | | score aligned nodes; branch noise can still add bad refs |
| E. missing nodes | | yes | | coverage + `unknown`, never forced zero |
| F. different granularity | | yes | | capped direct broader/narrower evidence |
| G. different graph sizes | | yes | | one-to-one normalized matching |
| H. domain substitution | | | no | useful knowledge can be legitimately disjoint; structure must carry analogy |
| I. extraction mistakes | | yes | | confidence, resolver rejection, and abstention |

### Retrieval vs Verification

**EXPENSIVE VERIFICATION first.** Apply the knowledge channels after structural
candidate retrieval and alignment. Do not mix them into one resonance scalar in
v0.1; report them beside structural and semantic evidence. `K_supply` is
directional and is especially relevant to complementary mode.

If a later corpus has enough high-confidence annotations, exact `requires` and
`about` IDs can have sparse inverted postings for a *supplemental* candidate
channel. Use document-frequency cutoffs and require structural verification.
Do not expand ontologies at query time or require this channel for recall.

### Computational Cost

With at most eight references per bucket, a node-pair matrix has at most 64
entries and assignment is `O(8^3)` with a standard solver. Even 100 aligned node
pairs across each of 20 candidates is negligible beside graph alignment.
Resolver lookup is `O(1)` from a pinned cache; a one-hop adjacency check is
bounded by the allowlist.

At one million Thoughts, optional exact-anchor retrieval is an inverted-index
lookup plus postings traversal. Generic/high-document-frequency anchors must be
suppressed. A live Wikidata/OpenAlex query per comparison is operationally and
scientifically unacceptable: it is slow, mutable, and not reproducible.

### Existing Implementations

- **Wikidata** supplies stable item/property identifiers, statement qualifiers,
  references, and ranks. It is broad but not a clean prerequisite ontology;
  cache only reviewed IDs/edges.
- **OpenAlex Topics** are an active four-level aboutness hierarchy; legacy
  Concepts are deprecated and frozen. Topics are predicted from works, so they
  are candidates for `about`, not evidence of `requires`.
- **ACM CCS 2012** is a useful computing-domain subject taxonomy and supports
  weighted classification, but it also describes publication content rather
  than prerequisites.
- **SKOS** provides the correct vocabulary for internal hierarchy and
  cross-scheme exact/close/broad/related mappings.
- **RDFLib** can parse RDF/SKOS snapshots; **NetworkX** can prototype bounded
  traversal; **SciPy `linear_sum_assignment`** provides production-grade
  rectangular one-to-one assignment. The first probe needs none of them and is
  Python-standard-library only.

Dependency risk is dominated by source drift and mapping quality, not the
matching implementation. Pin source snapshots and hashes; never let a public
endpoint silently change historical scores.

### Minimal Pseudocode

```text
knowledge_channels(query_alignment, candidate_alignment, resolver):
    for each aligned node pair (q, c):
        QA, QR = resolve(q.about), resolve(q.requires)
        CA, CR = resolve(c.about), resolve(c.requires)
        about  += soft_dice(max_bipartite(QA, CA))
        req    += soft_dice(max_bipartite(QR, CR))
        q_to_c += soft_dice(max_bipartite(QR, CA))
        c_to_q += soft_dice(max_bipartite(CR, QA))
    return channels + matched_ids + coverage + resolver_hash
```

### Toy Experiment

The executable probe is
`research/experiments/R0_E_repeat_knowledge_dna_probe.py`:

```bash
python3 research/experiments/R0_E_repeat_knowledge_dna_probe.py
```

Observed: `PROBE_STATUS: PASS (12/12 contract assertions)`. The role-blind
baseline scored a same-topic/different-requirements pair `0.333`, while the
required channel correctly scored `0.0`; different words with the same
requirement scored `1.0`; a generic shared hub changed from role-blind `1.0` to
`unknown`; a reviewed cross-scheme exact map scored `1.0`; and directional
`requires→about` complementarity scored `1.0`. Cross-domain structural analogy
correctly remained `0.0` in this channel and therefore must not be penalized.

This only falsifies interface/scoring mistakes, not annotation quality. The
two-hour empirical kill test is 30 independently labelled Thought-node pairs:
10 shared requirements, 10 same-topic/different-requirements hard negatives,
and 10 directional supply cases. Compare role-blind aboutness Jaccard with
automatically extracted `K_requires/K_supply`. Require macro AUPRC `>=0.75`, at
least `+0.15` over the baseline, and false-positive rate `<=0.10` on hard
negatives. If either annotator agreement is below `0.7` Cohen's kappa or the
model misses those gates, keep Knowledge DNA manual/optional and do not use it
for ranking.

### Failure Modes

1. **Topic/prerequisite conflation:** a paper about batteries is not evidence
   that battery knowledge is required by every branch.
2. **Generic hubs:** `engineering`, `system`, or `science` create massive false
   overlap unless frequency-filtered.
3. **Ontology shortcuts:** two concepts share a short path only because one
   taxonomy branch is coarse or multiply inherited.
4. **Cross-domain suppression:** treating disjoint knowledge as negative erases
   the exact analogies Resonance seeks.
5. **Missing-as-zero:** sparse annotations make a well-matched pair appear
   unrelated instead of unknown.
6. **Sense/linking error:** a stable identifier makes a wrong disambiguation
   reproducibly wrong.
7. **Version drift:** changing topics/crosswalks changes scores without either
   Thought changing.
8. **Anchor stuffing:** many near-duplicate refs can inflate naive averages;
   deduplication and one-to-one matching are required.
9. **Resource popularity loop:** citations or famous experts measure visibility,
   not knowledge fit.
10. **Privacy inference:** mapping required knowledge to named experts can reveal
    sensitive interests or falsely imply competence.

### What NOT To Build

- a universal ontology or ingestion pipeline;
- a knowledge-graph embedding model (TransE/RDF2Vec) before labelled evidence;
- live SPARQL/API calls in retrieval or verification;
- untyped flattening of `about` and `requires`;
- arbitrary shortest-path similarity over all external edge types;
- a single fused score that penalizes missing/disjoint knowledge;
- resource, citation, or expert recommendation inside Knowledge DNA v0.1;
- automatic claims of expertise from a person's Thought annotations.

### Architecture Consequences

1. Preserve the accepted `knowledge.about` / `knowledge.requires` split.
2. Keep knowledge optional; represent absent evidence as unknown.
3. Score exact IDs first and expose all contributing matches.
4. Version and hash resolver snapshots/crosswalks in scoring provenance.
5. Add one-to-one matching before enabling near-concept expansion.
6. Suppress generic anchors using corpus frequency or curated policy.
7. Use `requires→about` as a directional complementarity signal.
8. Condition verification scores on aligned nodes/subgraphs.
9. Keep knowledge channels separate from structural resonance until calibrated.
10. Make automatic required-knowledge extraction pass the hard-negative kill
    test before it can influence ranking.

### Sources

1. [Wikidata data model](https://www.wikidata.org/wiki/Help:Data_model) —
   authoritative identifier/statement model, including qualifiers, references,
   ranks, and the warning that statement context matters.
2. [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/) — normative
   hierarchy and cross-scheme mapping semantics; crucially, `closeMatch` and
   related mappings are not transitive.
3. [OpenAlex Topics](https://help.openalex.org/data/topics/) and
   [Concept deprecation](https://help.openalex.org/data/concepts/) — authoritative
   current aboutness hierarchy and evidence that legacy Concepts should not be
   a new dependency.
4. [ACM CCS classification guidance](https://www.acm.org/binaries/content/assets/publications/article-templates/ccs-howto-v6-12jan2015.pdf)
   — authoritative subject classification tree and relevance weights; useful
   for aboutness, not prerequisites.
5. [Schema.org `competencyRequired`](https://schema.org/competencyRequired) —
   an existing authoritative distinction for knowledge/skill needed to
   understand or perform something.
6. [Resnik, 1995](https://www.ijcai.org/Proceedings/95-1/Papers/059.pdf) — primary
   result explaining why uniform taxonomy edge counts are unreliable and why
   information content is the principled later alternative.
7. [Lin, 1998](https://mlanthology.org/icml/1998/lin1998icml-information/) —
   primary normalized information-theoretic similarity formulation.
8. [SciPy `linear_sum_assignment`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)
   — maintained implementation of rectangular maximum-weight assignment.
9. [RDFLib Graph](https://rdflib.readthedocs.io/en/latest/apidocs/rdflib.graph/)
   and [NetworkX shortest paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)
   — mature prototyping tools for pinned RDF snapshots and bounded traversal.
10. [Bordes et al., 2013, TransE](https://papers.neurips.cc/paper_files/paper/2013/hash/1cecc7a77928ca8133fa24680a88d2f9-Abstract.html)
    — primary scalable knowledge-graph embedding method; useful context for the
    explicitly deferred, training-dependent path.
