---
mission: R0-E
run: R0-E
contributor: Parshkov
agent_or_model: xAI Grok 4.6 (Grok Build TUI; more specific mode label not exposed)
date: 2026-08-30
mission_modified: false
web_research_used: true
blind_constraints_preserved: not-applicable
blind_sibling_exposure: none
agent_id: parshkov-xai-grok46-k3e8
tools_used:
  - Wikidata wbsearchentities / wbgetentities (live Q-ID and P279 lookup)
  - local Python set-overlap toy scorer
  - web research of primary API/docs and papers
---

# Decision

**GO**, with a constrained role: Knowledge DNA v0.1 is a dual-field bag of namespaced concept IDs (`about` vs `requires`) whose primary coordinate system is Wikidata Q-IDs. It is an *independent typing and complementary-recall signal*, not the analogical matcher and not a universal ontology. Score overlap with IDF-weighted Jaccard on specific concepts; downweight generic/role nouns; never put live SPARQL on the comparison path. Books, papers, courses, patents, datasets, tools, and experts attach later to *concepts*, not to Thought nodes.

# Confidence

**MEDIUM.** The typing role follows directly from Structure-Mapping (relations, not object attributes, carry analogy) and from MAC/FAC (content overlap retrieves surface-similar cases). The main uncertainty is extraction: entity linking from noisy LLM node labels will attach wrong or overly generic Q-IDs, and that error can fake knowledge overlap. The toy scorer used hand-linked IDs, so it tests the *interface*, not production linking.

# Best Algorithm / Method

**Knowledge DNA v0.1** is three pieces: a tiny annotation schema, a cheap set scorer, and a hard split between knowledge-as-coordinates and structure-as-relations.

**1. What a node points to.** Each Thought node may carry zero or more `ConceptRef` values:

```text
ConceptRef := <namespace>:<id>
namespaces  := wd | openalex | acmccs | local
```

Primary namespace for v0.1: `wd:Q…` (Wikidata items). Optional overlays, not required for the first benchmark: `openalex:T…` (OpenAlex Topics) on scholarly thoughts; `acmccs:…` on computing thoughts. Do not use deprecated OpenAlex Concepts.

**2. Two fields, not one.**

| Field | Meaning | Example on “SEI growth causes capacity fade” |
|---|---|---|
| `about` | What this node *denotes* | `wd:Q120906754` solid electrolyte interphase |
| `requires` | Knowledge needed to *understand or solve* it | `wd:Q2822895` lithium-ion battery, `wd:Q568` lithium |

These are different. Liang et al. recover prerequisite edges among concepts from course dependencies; Pan et al. treat MOOC concept order as a DAG of “must know X before Y.” `about` is topical denotation. `requires` is that prerequisite/skill coordinate. Mixing them collapses complementary resonance into “same topic.”

**3. Scoring.** Let \(A, B\) be sets of concept IDs (graph-level unions of node fields, or node-restricted). Let \(\mathrm{idf}(c)=w_{\mathrm{gen}}\) if \(c\) is generic/role-like, else \(1\).

\[
s(A,B)=\frac{\sum_{c\in A\cap B}\mathrm{idf}(c)}{\sum_{c\in A\cup B}\mathrm{idf}(c)}
\]

Channels:

- \(K_{\mathrm{about}}=s(\mathrm{about}_A,\mathrm{about}_B)\)
- \(K_{\mathrm{req}}=s(\mathrm{requires}_A,\mathrm{requires}_B)\)
- \(K_{\mathrm{comp}}(A\!\to\!B)=s(\mathrm{requires}_A,\mathrm{about}_B)\) (asymmetric)

Nearby but non-identical concepts: optionally expand each ID by **cached** Wikidata `P279` (subclass of) parents, depth 1, before \(s\). Do **not** query `query.wikidata.org` per comparison (60 s timeout, ~5 concurrent queries/IP, 60 s CPU/60 s quota). Nearby expansion is a cached parent table of the IDs we actually stored, built offline from `wbgetentities` or a dump slice.

**4. How the score is used.** Combine with the structural verifier, do not replace it:

```text
high structure  + high K_about  → direct / same-domain resonance
high structure  + low  K_about  → analogical resonance
low/moderate structure + high K_comp(A→B) → complementary (A needs what B is about)
```

This is Gentner’s distinction in operational form: analogy maps relations and *drops* object attributes. Knowledge overlap is the attribute/content channel. If Knowledge DNA were the analogical retrieval key, the battery/organization pair would be designed to miss.

**5. Resources.** A paper (`openalex:W…` / DOI), course, patent, dataset, tool, or expert is a *resource hanging off a concept*, not a Thought-DNA field. OpenAlex Works/Authors are the scholarly resource graph; Wikidata already links many items to described-by-source (`P1343`) and identifiers. v0.1 stores none of that on the Thought node.

# Why It Fits Resonance

The project’s hard negative is “same words, different structure” vs “different words, same structure.” Knowledge DNA attacks a third axis the structural engine is not supposed to fake: *same required knowledge, different wording* and *same structure, different knowledge*. Cross-domain analogy is defined by the second of those. Complementary matching (“your missing method is my current thought”) is defined by \(K_{\mathrm{comp}}\), which structural isomorphism will not see.

MAC/FAC’s first stage uses content vectors and therefore prefers surface-similar remindings. Resonance wants analogical recall from *relational fingerprints* (mission B), then expensive structural verification (mission C). Knowledge overlap is the cheap extra posting-list that recovers same-domain and complementary candidates the fingerprint index may under-call. It is not a second Shazam.

It also respects the project’s own `WHY_NOT.md`: do not build a universal knowledge graph first. Wikidata and OpenAlex already exist. We store a handful of their IDs.

# Required Thought DNA

Only fields the scorer uses. Nothing else.

**On a node (all optional, missing = empty set):**

- `knowledge.about[]`: 0–8 `ConceptRef`, each with `id`, `conf` ∈ [0,1], `via` (`wbsearchentities` | `extractor` | `human`)
- `knowledge.requires[]`: 0–8 `ConceptRef`, same shape

**On a graph (derived, not independently authored):**

- `knowledge.about` := union of node `about`
- `knowledge.requires` := union of node `requires`

**Not in v0.1 Thought DNA:** resource lists, embeddings, prerequisite DAGs, Wikidata dumps, OpenAlex works, descriptions, aliases, P31/P279 closures (those live in a side cache keyed by ID).

**Annotation rule:** put *domain concepts* in Knowledge DNA. Put *roles* (degradation, failure, accumulation, system, process, problem) in the typed Thought Graph as node/edge types. Leaking roles into `about` makes analogies look knowledge-similar.

# Required Graph Representation

Directed typed property graph. Knowledge refs are **node properties**, not extra graph edges into Wikidata. We do not join the Thought Graph to Wikidata at match time. A hypergraph is unnecessary: one node can hold a small set of concept IDs. Multigraph only if the structural missions independently require parallel typed edges.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---|---|---|---|
| A paraphrase | ✓ | | | Same Q-ID after linking; labels never compared |
| B vocabulary substitution | ✓ | | | Q-IDs are language-agnostic (`battery` / `аккумулятор` → `wd:Q267298`) |
| C node ordering | ✓ | | | Sets; order ignored |
| D irrelevant branches | ✓ | | | Union + IDF: junk generic IDs downweighted; unused specific IDs dilute \(s\) only mildly |
| E partial / missing nodes | | ✓ | | Missing annotations → empty sets → \(s=0\), i.e. “no knowledge evidence,” not a penalty on structure |
| F different granularity | | ✓ | | Depth-1 cached `P279` parents (`wd:Q2822895` ⊂ `wd:Q187510` ⊂ `wd:Q267298`). Deeper paths and OpenAlex domain/field/subfield rollup are optional overlays |
| G different graph sizes | ✓ | | | Set Jaccard is size-normalized; cap 8 IDs/node so large graphs cannot flood |
| H domain substitution, relations preserved | | | ✓ *as a match* | **Intended miss** on \(K_{\mathrm{about}}\). That miss *classifies* the pair as analogical when structure is high |
| I modest extraction mistakes | | ✓ | | `conf` threshold (drop `<0.5`); IDF; reject generic IDs. Wrong specific ID is a real miss/false overlap |

# Retrieval vs Verification

**BOTH, in different modes — never as analogical MAC.**

| Mode | Where | Index | Output |
|---|---|---|---|
| Same-domain recall | FAST RETRIEVAL | inverted index: specific `about` IDs → thought IDs | candidate posting lists |
| Complementary recall | FAST RETRIEVAL | inverted index: `requires` IDs → thoughts whose `about` contains that ID | directed candidates \(A\to B\) |
| Analogical recall | **not here** | structural fingerprints (mission B) | — |
| Typing / explanation | VERIFICATION side-channel | no extra index | \(K_{\mathrm{about}}, K_{\mathrm{req}}, K_{\mathrm{comp}}\) plus the matched ID lists |

Verifier input: two graphs’ Knowledge DNA sets plus the structural correspondence (from mission C). Verifier output adds a typed resonance record: matched concept IDs, unmatched required IDs, and the three scores. That is the explanation fragment “these branches share required knowledge X / these are analogous because structure matches and knowledge does not.”

# Computational Cost

Set operations on ≤800 IDs/graph (100 nodes × 8). A 50-vs-50 comparison is microseconds in CPython.

Top-20 candidate comparisons: still negligible next to graph alignment.

Corpus of 1M thoughts: inverted index with a few posting lists per thought. Posting-list intersection is the same cost model as a tiny search engine. Do not SPARQL 1M times. Do not load Wikipedia2Vec or REL dumps for MVP.

Offline cache: one `wbgetentities` batch per newly seen Q-ID for label + `P279` parents. Wikimedia etiquette (named User-Agent, no bulk via live API; dumps if we ever need the full subclass graph).

# Existing Implementations

| Piece | Use in v0.1 | Maturity / risk |
|---|---|---|
| Wikidata Action API `wbsearchentities` / `wbgetentities` | resolve labels → Q-IDs; fetch P279 | production; User-Agent required; not for bulk |
| Wikidata Query Service SPARQL | **not on hot path** | 60 s timeout; 5 concurrent; throttling; graph split (scholarly vs main) |
| `qwikidata` | optional Python wrapper | thin; API shape can drift — raw `requests` is enough |
| OpenAlex Topics API + `pyalex` | optional scholarly overlay | production; Concepts **deprecated**; Topics are inferred aboutness of works, not a general world ontology |
| ACM CCS 2012 SKOS | optional CS overlay | stable, small, computing-only |
| REL (van Hulst et al. 2020) | **reject for MVP** | SOTA entity linker; needs Wikipedia dump + models |
| Wikipedia2Vec (Yamada et al. 2016) | optional later near-concept cosine | heavy pretrained embeddings |
| ConceptNet Numberbatch (Speer et al. 2017) | **reject as primary IDs** | word/phrase vectors, not stable concept IDs |

# Minimal Pseudocode

```python
GENERIC = {"wd:Q35120", "wd:Q58778", "wd:Q3249551", "wd:Q1121708",
           "wd:Q621184", "wd:Q11028", "wd:Q488383"}  # entity, system, process, ...
ROLE    = {"wd:Q94643648"}  # degradation — structural role, not a domain concept
W_GEN, W_ROLE = 0.15, 0.30

def idf(c):
    if c in GENERIC: return W_GEN
    if c in ROLE:    return W_ROLE
    return 1.0

def weighted_jaccard(A, B):
    A, B = set(A), set(B)
    if not A or not B: return 0.0
    num = sum(idf(c) for c in A & B)
    den = sum(idf(c) for c in A | B)
    return num / den if den else 0.0

def expand(ids, parents):          # parents: id -> cached P279 list
    out = set(ids)
    for i in ids:
        out.update(parents.get(i, ()))
    return out

def knowledge_scores(g1, g2, parents, use_hop=True):
    a1, a2 = g1.about, g2.about
    r1, r2 = g1.requires, g2.requires
    if use_hop:
        a1, a2 = expand(a1, parents), expand(a2, parents)
        r1, r2 = expand(r1, parents), expand(r2, parents)
    return {
        "K_about": weighted_jaccard(a1, a2),
        "K_req":   weighted_jaccard(r1, r2),
        "K_comp":  weighted_jaccard(r1, a2),   # g1 needs what g2 is about
    }

def type_resonance(K_about, structure_ok, K_comp, t_about=0.25, t_comp=0.40):
    if structure_ok and K_about >= t_about: return "direct"
    if structure_ok and K_about <  t_about: return "analogical"
    if K_comp >= t_comp:                    return "complementary"
    return "none"

# retrieval (same-domain / complementary only)
# index: specific about-id -> [thought_id]
# query G: union posting lists of G.about (idf > W_ROLE), take top-k by K_about
# complementary: union posting lists of thoughts whose about contains G.requires
```

# Toy Experiment

**Claim to kill:** “Bag-of-Q-ID overlap is a safe analogical signal,” or the opposite, “knowledge overlap cannot separate same-domain paraphrase from cross-domain analogy.”

Hand-link four packs with live `wbsearchentities` IDs (looked up 2026-08-30). Score only Knowledge DNA; do not run a structural matcher. Metric: \(K_{\mathrm{about}}\) and \(K_{\mathrm{comp}}\). Implementable in <30 minutes; this run used local Python only.

| Pack | Graphs | Expect |
|---|---|---|
| Analogy | Li-ion thermal runaway vs org information overload | \(K_{\mathrm{about}}<0.25\), \(K_{\mathrm{comp}}=0\) |
| Paraphrase | two battery-degradation wordings | \(K_{\mathrm{about}}\ge 0.40\) |
| Same words, different field | WL/graph-isomorphism vs graph-kernel chemoinformatics | \(K_{\mathrm{about}}\) moderate (shared `wd:Q39045684` only), \(K_{\mathrm{req}}=0\) |
| Complementary | “I need an aligner” (`requires` OT+GW) vs “I am working on GW” | \(K_{\mathrm{about}}=0\), \(K_{\mathrm{comp}}\ge 0.50\) |

**Observed (IDF-weighted Jaccard, no hop unless noted):**

| Pack | \(K_{\mathrm{about}}\) | \(K_{\mathrm{req}}\) | \(K_{\mathrm{comp}}\) |
|---|---|---|---|
| Analogy | 0.111 (shared role `degradation`) / **0.000 if role stripped** | 0.000 | 0.000 |
| Paraphrase | **0.500** | 0.667 | 0.167 |
| Same words, different field | 0.250 | 0.000 | 0.000 |
| Complementary | 0.000 | 0.333 | **0.667** (`wd:Q140626363`, `wd:Q1280998`) |

**Generic-motif attack:** add `system`, `process`, `failure` to both analogy graphs. Unweighted Jaccard rises to **0.333**; IDF-weighted stays **0.153**. Unweighted bags fail; IDF + role-stripping is what makes the GO hold.

**Falsify the recommendation if** a second annotator, following the domain-concept rule, gets analogy \(K_{\mathrm{about}}\ge 0.25\) or paraphrase \(K_{\mathrm{about}}<0.40\) on this four-pack.

# Failure Modes

1. **Generic motif collision.** Both graphs tagged `entity`/`system`/`process`/`failure` → false knowledge match on every analogy. Mitigation: GENERIC stoplist + IDF; better: do not store those IDs.
2. **Role leak.** `degradation` as `about` on battery *and* organization (this run: 0.111 residual). Roles belong in structure.
3. **Linker polysemy.** `battery` → electrochemical cell `wd:Q267298` vs artillery; `lithium` → Nirvana song `wd:Q1130059` vs element `wd:Q568`. First `wbsearchentities` hit is unsafe.
4. **Empty annotations.** Extraction skips linking → \(K=0\) everywhere → Knowledge DNA adds no signal and cannot type analogical vs direct. Structure-only fallback must remain valid.
5. **Same words, different referent.** “Graph matching” in CS vs chemoinformatics shares `wd:Q39045684` (this run: 0.250). Knowledge DNA alone will not make the hard negative; the structural/typed graph must still differ.
6. **Complementary direction.** \(K_{\mathrm{comp}}(A\to B)=0.667\) while \(B\to A=0\). Symmetric cosine would hide who needs whom.
7. **SPARQL-in-the-loop.** Per-pair subclass queries will 429/timeout long before 1M thoughts.
8. **OpenAlex Concepts.** Deprecated MAG-derived Wikipedia concepts, high recall/low precision; Topics are a different inferred hierarchy. Using Concepts as if they were Wikidata will rot.

# What NOT To Build

- A hosted universal ontology or Wikidata replica for MVP (`WHY_NOT.md`).
- Knowledge similarity as analogical retrieval (would miss battery/organization by construction; MAC/FAC content vectors already make this psychological mistake).
- LLM-as-judge “do these thoughts require the same knowledge?”
- ConceptNet / Numberbatch as the ID space (words, not concepts).
- REL + Wikipedia dumps + Wikipedia2Vec as a v0.1 dependency.
- Training TransE/GNN knowledge-graph embeddings.
- Storing papers/books/experts on Thought nodes.
- ACM CCS or OpenAlex Topics as the *global* coordinate system (domain-narrow or scholarly-only).
- Live SPARQL or full `P31/P279*` closures at compare time.
- A single undifferentiated `topics[]` field.

# Architecture Consequences

1. Thought DNA v0.1 gets `knowledge.about[]` and `knowledge.requires[]` as optional node properties of namespaced IDs; default empty.
2. Cap 8 refs/field/node; drop `conf<0.5`; drop GENERIC IDs at write time.
3. Relational roles (failure, degradation, accumulation) are graph types, not knowledge IDs.
4. Retrieval: inverted index on specific `about` and `requires` IDs for same-domain and complementary modes only.
5. Analogical retrieval stays structural; Knowledge DNA *classifies* analogical vs direct after structure hits.
6. Explanation payload includes the matched ID lists and \(K_{\mathrm{comp}}\) direction.
7. Side cache: Q-ID → {label, P279 parents}, filled by `wbgetentities`, never by SPARQL in the matcher.
8. Overlays (`openalex:T…`, `acmccs:…`) are additive namespaces, not a second scorer in v0.1.
9. Resources attach to concepts in a later layer; they do not block freezing Thought DNA.
10. Benchmark G must include: analogy (low \(K_{\mathrm{about}}\)), paraphrase (high \(K_{\mathrm{about}}\)), generic-motif attack, complementary direction, and a polysemy linker trap.

# Sources

1. **Gentner, D. (1983).** Structure-mapping: A theoretical framework for analogy. *Cognitive Science* 7(2), 155–170. Analogy maps relations, not object attributes — knowledge overlap is the attribute channel we must *not* use as analogical identity.
2. **Forbus, K. D., Gentner, D., & Law, K. (1995).** MAC/FAC: A model of similarity-based retrieval. *Cognitive Science* 19(2), 141–205. Content vectors retrieve surface-similar cases; structural SME is the second stage. Directly warns against knowledge-first analogical MAC.
3. **Wikidata: SPARQL tutorial** and **Wikidata:Data access.** `P31` vs `P279`; Linked Data URIs `wd:Q…`; dumps vs live API. Defines the only parent relation v0.1 is allowed to cache.
4. **Wikidata Query Service/User Manual** (query limits). 60 s deadline, 60 s CPU/60 s/client, ~5 concurrent, 429 throttle. Why SPARQL is off the hot path.
5. **MediaWiki Wikibase API** (`wbsearchentities`, `wbgetentities`). The actual linking/cache API for MVP.
6. **Priem, J., Piwowar, H., & Orr, R. (2022).** OpenAlex: A fully-open index of scholarly works, authors, venues, and concepts. arXiv:2205.01833. Scholarly resource graph; original Concepts were Wikidata-linked MAG terms.
7. **OpenAlex Topics documentation (2026).** Concepts deprecated; Topics are inferred aboutness (4 domains / 26 fields / 252 subfields / ~4,516 topics) with optional Wikipedia IDs — overlay, not world ontology.
8. **ACM (2012).** Computing Classification System. Polyhierarchical SKOS, computing-only. Safe optional namespace, unsafe global one.
9. **Liang, C., Wu, Z., Huang, W., & Giles, C. L. (2015).** Measuring prerequisite relations among concepts. *EMNLP*. RefD on Wikipedia links. Evidence that “required before” is a distinct relation from co-topic.
10. **Liang, C., Ye, J., Wu, Z., Pursel, B., & Giles, C. L. (2017).** Recovering concept prerequisite relations from university course dependencies. *AAAI*. Operational split of course-level vs concept-level prerequisites — the `requires` field.
11. **van Hulst, J. M. et al. (2020).** REL: An entity linker standing on the shoulders of giants. *SIGIR*. Exists, works, too heavy for 40–50 h MVP.
12. **Yamada, I. et al. (2016).** Joint learning of the embedding of words and entities. *CoNLL* / Wikipedia2Vec. Optional later near-duplicate concept cosine; not v0.1 storage.

Wikidata IDs used in the toy pack were resolved with `wbsearchentities` on 2026-08-30, including `wd:Q2822895` lithium-ion battery, `wd:Q908282` thermal runaway, `wd:Q43229` organization, `wd:Q1130191` information overload, `wd:Q140626363` Gromov-Wasserstein Distance, `wd:Q1280998` optimal transport.
