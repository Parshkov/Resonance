---
mission: R0-H
run: R0-H
contributor: Parshkov
agent_or_model: xAI Grok 4.6 (Grok Build TUI; more specific mode label not exposed)
date: 2026-08-31
mission_modified: false
web_research_used: true
blind_constraints_preserved: not-applicable
blind_sibling_exposure: none
agent_id: parshkov-xai-grok46-k3e8
tools_used:
  - web research of primary papers (Wang 2003 PDF; Gentner 1983 PDF; MAC/FAC, SME, Gick & Holyoak, Chalmers et al., WL, GW/FGW, entity-linking, LLM extraction)
  - local Python typed-path fingerprint collision check
notes: >
  Same agent_id authored canonical R0-E (PR #23, pending review). The Knowledge DNA
  attack is therefore not independent of that run. This red team did not open
  merged submissions R0-A, R0-B2, R0-C2, or R0-D, nor PR #24 (B1). Coordination
  scan of issue #5 included B2's SUBMIT summary (QUALIFIED GO; ~15 bits vs Wang's
  30; two unblended channels). Entropy numbers below are recomputed from Wang
  2003 §2.2 and a 6×8 role/relation vocab, not copied from that summary.
---

# Decision

**QUALIFIED NO-GO** on the candidate architecture as stated. The two-stage cheap-filter / expensive-verifier split survives; the Shazam-style *structural* fingerprint as the cheap analogical index does not. Wang's (2003) hashes carry ~30 bits and vote on a one-dimensional time offset. Typed-path fingerprints of 10–100 node Thought Graphs carry ~6–14 bits, vote on a permutation, and the project's own example motif (`accumulates → causes → causes`) collides at Jaccard 1.0 across battery, organization, marriage, technical debt, and eutrophication. MAC/FAC and Gick & Holyoak both place analogical reminding as rare without surface cues; putting structure in stage 1 inverts the only retrieval architecture that is both psychologically attested and computationally cheap. Knowledge DNA is a same-domain overlay, not analogical signal, and is dominated by entity-linking error. LLM relation extraction is too unstable to fingerprint. Simplest alternative: content / knowledge-ID retrieval + a small SME-lite verifier. Treat 1M-scale analogical recall as a later question, after extraction is shown to reproduce itself.

# Confidence

**HIGH** on the Shazam mathematical break and on generic-motif collision (recomputed from Wang; toy below). **MEDIUM** on “abandon the engine”: a content-first MAC/FAC loop can still distinguish same-words/different-structure once two graphs are in working memory, and that is the project's hard negative. Main uncertainty: whether a *rare* higher-order motif channel plus quantized node semantics could reach ~20 bits without destroying domain-substitution invariance. C1 is still unsubmitted; verifier cost is not a current kill.

# Best Algorithm / Method

**Attack, not a new matcher.** Three independent cheap falsifiers.

**1. Hash entropy (Wang 2003 §2.2).** Spectrograms are reduced to peaks; combinatorial hashes pack two frequencies plus \(\Delta t\) into ~30 bits. Insufficient entropy “leads to excessive and spurious matches … requiring more processing power to cull.” Scoring is a histogram of \(\delta t = t'_k - t_k\): one scalar offset. Thought Graphs have no such axis. Correspondence is a partial permutation of \(\sim 50\) nodes. The graph analogue of the offset histogram is geometric hashing / RANSAC over maps, not a 1-D bin scan.

Role-typed length-2 paths over 6 roles × 8 relations occupy \(6\cdot8\cdot6\cdot8\cdot6 = 13824\) keys (\(\approx 13.8\) bits). Relation-only pairs occupy \(8^2=64\) keys (6 bits). At corpus \(N=10^6\) and \(H\approx 2\) hashes/thought, expected postings per role-path key \(\approx 145\); per relation-pair key \(\approx 3\cdot 10^4\). Wang's 30-bit key at the same \(N,H\) has expected postings \(\approx 0\).

**2. Motif collision (toy).** Five domain-substituted “accumulation → degradation → failure” graphs share identical role-path bags (Jaccard 1.0). IDF cannot save them: the shared keys *are* the common ones. Filtering generic motifs to restore precision leaves analogical recall with no remaining keys. That is entropy starvation, not a tuning issue.

**3. Retrieval psychology.** Forbus, Gentner & Law (1995): in retrieval, superficial similarity dominates; purely analogical remindings are occasional. MAC is a content-vector dot product; FAC is SME. Gick & Holyoak (1980, 1983): fortress→tumor transfer is ~10% with no analog, ~20–30% with an analog and no hint, ~75% after a hint to use the story. The bottleneck is *noticing*, not mapping. A structural first-stage index is trying to do what humans (and MAC) do not.

**Alternative to implement if the Shazam layer is killed:**

```text
probe  →  embedding ∪ knowledge-ID posting lists     [MAC]
       →  top-K (K≈20)
       →  greedy 1-1 relational matcher + systematicity [FAC]
       →  explanation = mapping ∪ unmatched branches
```

Do not index analogical identity. Index content. Verify structure.

# Why It Fits Resonance

The project's distinctive claim is not “two-stage retrieval exists.” MAC/FAC already is that. The distinctive claim is that *relational fingerprints* retrieve cross-domain analogs the way Shazam retrieves a song. That claim is what fails: not enough bits, no alignment axis, generic motifs are the analogical signal, and analogical retrieval without content is empirically rare.

What remains useful is exactly WHY_NOT plus SMT: embeddings collapse same-words/different-structure; an LLM judge is unreproducible; exact isomorphism is too brittle. Those arguments justify a *verifier*, not a Shazam index.

# Required Thought DNA

Only fields the surviving pipeline uses. Do not add fingerprint-specific packing.

**Node:** `id`; short label; coarse `role` (problem, mechanism, state, outcome, constraint, method, resource, agent); optional `about`/`requires` concept IDs with confidence; `source_span`; `extract_conf`.

**Edge:** typed relation from a closed v0.1 set (`causes`, `prevents`, `requires`, `supports`, `part_of`, `constrains`, `produces`, `contradicts`); polarity; `source_span`; `extract_conf`.

**Graph-level:** provenance to source text; extractor id/version (self-match tests need this).

Higher-order `CAUSE[R1,R2]` is what systematicity actually scores (Gentner 1983; Falkenhainer et al. 1989). Binary edges are a lossy stand-in: reify only if the verifier consumes nested predicates. Do not add hash fields, WL colors, or GW costs to DNA.

# Required Graph Representation

Directed typed property graph, optionally with reified statements so a relation can itself be an argument of `causes`/`implies`. Not a tree (DAGs and shared nodes occur). Not a hypergraph for v0.1. Not an embedding-only object: the verifier needs explicit edges.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---|---|---|---|
| A paraphrase | | yes | | content retrieval; verifier uses roles not tokens |
| B vocabulary substitution | | yes | | same, until linking/role errors |
| C node ordering | yes | | | graph, not sequence |
| D irrelevant branches | | yes | | FAC can ignore unmatched; retrieval IDF if content-based |
| E missing nodes | | yes | | partial mapping; path hashes die here if used |
| F granularity `A→B` vs `A→X→Y→B` | | | retrieval: no | path keys change; coarsen only in FAC, not in the index |
| G different graph sizes | | yes | | partial mapping |
| H domain substitution, relations preserved | | | as *retrieval* invariant | generic motifs match everything; true analogical recall is FAC after a content miss |
| I modest extraction mistakes | | | | relation instability (Uwasomba et al. 2026) moves hashes; self-match fails |

Desired invariances A–I cannot all sit in one hash. F and H are the pair that destroys a structural index: coarsening changes the key; domain substitution is the generic motif.

# Retrieval vs Verification

Candidate architecture: **BOTH** (structural fingerprints then alignment). **Kill the structural half of retrieval for MVP.**

- **FAST RETRIEVAL (keep):** embedding / BM25 on node labels + IDF-weighted knowledge-ID sets. Index: ANN + inverted posting lists on concept IDs. Output: top-K ids.
- **EXPENSIVE VERIFICATION (keep):** 1-1 mapping, relational consistency, systematicity (prefer connected higher-order structure). Output: correspondence, unmatched branches, a structured score — not a scalar.
- **DO NOT BUILD:** inverted index of typed path-shingles / WL colors / constellation hashes as the analogical recall path.

# Computational Cost

- **50 vs 50 FAC:** greedy seed-and-extend or SME-style match hypotheses are polynomial, typically \(O(n^2)\) on predicate pairs (Falkenhainer et al. 1989). Fine.
- **Top-20:** \(20 \times O(n^2)\) is the MVP budget. Entropic GW/FGW is \(O(n^3)\) per pair (Peyré; Scetbon, Peyré & Cuturi 2021) and returns a coupling that still needs rounding into a 1-1 map. Do not spend the 40-hour budget there.
- **1M corpus:** content ANN is the solved problem. Structural inverted lists at 14 bits are the unsolved one (hundreds of postings/key, no 1-D cull). MVP corpus will not be 1M thoughts; designing the index for that scale is premature.

# Existing Implementations

| Piece | Artifact | Maturity / risk |
|---|---|---|
| FAC / SME | QRG `sme` (Northwestern); described in Falkenhainer et al. 1989 | Research code; reimplement a 1-1 greedy subset rather than porting full SME |
| Content retrieval | `sentence-transformers`, BM25 (`rank_bm25`) | High; do not treat as analogical identity |
| Knowledge IDs | Wikibase `wbsearchentities`; OpenAlex Topics | Linking F1 on clean text is ~0.6–0.75 (van Noord et al. 2023 ReFinED 73.3%); short node labels will be worse |
| WL kernels | `grakel` | Linear in edges (Shervashidze et al. 2011); too coarse as analogical keys |
| FGW | `POT` (`ot.gromov.fused_gromov_wasserstein`) | Mature numerics; hyperparameter-sensitive; not an explanation |
| GED | `networkx.graph_edit_distance` | Exponential; oracle for n≲12 only |

# Minimal Pseudocode

```text
# NAIVE STRUCTURAL INDEX (do not ship)
fp(G):
  for each directed length-2 path u-r1->v-r2->w:
    emit (role(u), r1, role(v), r2, role(w))
retrieve(Q, corpus):
  return thoughts whose fp intersect fp(Q)   # posting lists explode / collide

# SURVIVING MVP
mac(Q, corpus, K=20):
  s_text  = ANN(embed(labels(Q)))
  s_know  = IDF_jaccard(about(Q) ∪ requires(Q))
  return top_K(s_text + s_know)

fac(Q, C):
  seeds = role-compatible node pairs with high label/concept sim
  extend 1-1 by typed-edge consistency
  score  = systematicity(connected mapped relations) - attribute_bonus
  return mapping, unmatched_Q, unmatched_C, score

resonance(Q):
  for C in mac(Q):
    yield fac(Q, C)
```

# Toy Experiment

**Falsify:** “sparse relational fingerprints retrieve the battery/organization analog without also retrieving unrelated generic-motif thoughts.”

**Inputs (13 graphs, typed roles + closed relations):** battery heat-fail; organization info-fail; marriage resentment-fail; tech-debt fail; lake eutrophication; reversed battery causation; heat-*prevents*-failure; fortress convergence; tumor convergence; two academic templates; complementary SEI-needs-model vs phase-field-model.

**Method:** bag of role-typed length-2 paths; unweighted and IDF Jaccard. Local Python, no network, <2 min.

**Observed:**

| Pair | role-path Jaccard | note |
|---|---|---|
| battery vs org / marriage / tech-debt / lake | **1.000** | intended analog = spurious analog |
| two paper templates | **1.000** | schema collision |
| battery vs reversed causation | **0.000** | hard negative separated (good) |
| battery vs prevents | **0.000** | polarity separated (good) |
| battery vs fortress | **0.000** | true analog *not* in the generic-motif bucket |

**Expected if the candidate were right:** battery–org high; battery–marriage low; fortress–tumor high without shared vocabulary.

**Metric that fails the candidate:** analogical precision@5 of a role-path posting-list query from `battery` among the 13. Observed: org, marriage, tech-debt, lake all tie with org. Precision among generic-motif distractors is 0.25 if org is the only intended hit.

**Pass/fail:** FAIL on analogical precision. PASS on the hard negative (reversed / prevents). The verifier, not the index, is what the hard negative needs.

# Failure Modes

At least the required ten pairs; these are attacks, not gold.

1. **Same words, reversed structure.** Battery: heat→degradation→failure vs failure→degradation→heat. Naive embeddings fire; a correct FAC must not.
2. **Same topic, different intent.** “Battery as energy reservoir” vs “battery as thermal hazard.” Knowledge IDs (`wd:Q267298`) collide; relations do not.
3. **Intended analog = generic motif.** Battery vs organization. Toy Jaccard 1.0 with marriage, tech-debt, lake.
4. **Spurious analog.** Battery vs marriage-resentment. Same role-path bag.
5. **Schema / template thoughts.** Any two IMRAD papers: problem→method→result→claim.
6. **True analog humans miss.** Fortress vs tumor. Content MAC misses; structural keys are either generic or extraction-fragile; Gick & Holyoak need a hint.
7. **Polarity flip.** `causes` vs `prevents` on the same nodes. Closed relation set is mandatory; open LLM relations will synonym-collapse them.
8. **Local yes, global no.** Two graphs share a length-2 causal chain and disagree on the governing higher-order goal. Path hashes vote match; there is no \(\delta t\) histogram to reject a globally inconsistent map.
9. **Granularity paraphrase miss.** `SEI→fade` vs `SEI→resistance→heat→fade`. Path fingerprints differ; true same-thought retrieval fails.
10. **Complementary ≠ analogical.** “I need a SEI growth model” vs “here is a phase-field interface model.” Structural overlap low; `requires`↔`about` is the signal; linking “interface” to the wrong Q-ID fakes it.
11. **Polysemy knowledge collision.** River bank vs bank run. Short labels, little context: Wikidata EL is exactly this failure (van Noord et al. 2023; metonym error ~31% even for ReFinED).
12. **Extraction self-mismatch.** Two greedy extracts of one paragraph (Uwasomba et al. 2026: relations more unstable than entities as temperature rises). If `fp(extract1) ∩ fp(extract2)` is not a self-hit, the index is hashing the extractor.

# What NOT To Build

- **Shazam constellation hashes over Thought Graphs.** No 1-D offset; not enough bits; Wang himself forbids low-entropy tokens.
- **WL / graphlet bags as analogical identity.** Cheap, and they classify graph *shape*. Thought analogy is a mapping, not a kernel value (Shervashidze et al. 2011).
- **FGW/GW as the v0.1 verifier.** NP-hard in general; entropic \(O(n^3)\); coupling ≠ inspectable 1-1 map; 40 hours will be spent on Sinkhorn hyperparameters.
- **Knowledge DNA as analogical retrieval.** Gentner: drop attributes. Overlap on Q-IDs is the attribute/content channel. Same-domain recall only.
- **Open relation vocabularies from the LLM.** Synonym drift (DSE-RE; Uwasomba) makes hashes non-reproducible.
- **Domain-substitution invariance in the index.** That invariance *is* generic-motif matching.
- **Training a GNN first.** WHY_NOT still holds; no labeled analogical maps; not explainable.
- **1M-scale structural index before extraction self-match.** Wrong scale, wrong layer.

# Architecture Consequences

1. Kill structural fingerprints as the analogical recall path for v0.1.
2. Keep two-stage MAC/FAC: content/knowledge retrieve, structure verify.
3. Put domain-substitution (invariance H) only in FAC, never in the index.
4. Put granularity (invariance F) in optional contraction before FAC, not in hashes.
5. Closed relation set with polarity; provenance spans; extractor version.
6. Knowledge IDs remain a same-domain / complementary overlay (`about` vs `requires`), not analogical identity. Empty set = no evidence.
7. Benchmark G must include: generic-motif pack (battery/org/marriage/debt/lake), polarity, reversed causation, fortress/tumor, two-extract self-match, paper-template pair.
8. PASS/FAIL for retrieval: analogical precision@K on the generic-motif pack. If org does not outrank marriage, the index is not analogical.
9. Do not wait for 1M thoughts; brute-force FAC on a same-day corpus is enough to test the hard negative.
10. Abandon or radically revise the engine if (a) two extracts of one thought are not each other's nearest structural neighbor, or (b) generic-motif false-positive rate at FAC stays high after 1-1 + systematicity. Either result says the representation, not the index, is the object.

# Sources

1. Wang, A. L. (2003). *An Industrial-Strength Audio Search Algorithm.* ISMIR. Hash entropy, 30-bit combinatorial tokens, \(\delta t\) histogram, low-entropy warning. **Why:** states the conditions Shazam needs that Thought Graphs lack.
2. Gentner, D. (1983). Structure-mapping. *Cognitive Science, 7*, 155–170. Relations not attributes; systematicity; analogical-shift (literal similarity more accessible). **Why:** analogical identity is not content overlap; retrieval accessibility is against structural keys.
3. Falkenhainer, B., Forbus, K. D., & Gentner, D. (1989). The structure-mapping engine. *Artificial Intelligence, 41*, 1–63. Higher-order `CAUSE`; ~\(O(N^2)\). **Why:** the verifier to keep; binary graphs omit what systematicity scores.
4. Forbus, K. D., Gentner, D., & Law, K. (1995). MAC/FAC. *Cognitive Science, 19*, 141–205. Content-vector MAC; SME FAC; analogical reminding rare. **Why:** the two-stage split Resonance already named, with structure *not* in stage 1.
5. Gick, M. L., & Holyoak, K. J. (1980). Analogical problem solving. *Cognitive Psychology, 12*, 306–355; (1983) Schema induction. *Cognitive Psychology, 15*, 1–38. Fortress/tumor; hint required. **Why:** analogical retrieval is the bottleneck even for humans.
6. Chalmers, D. J., French, R. M., & Hofstadter, D. R. (1992). High-level perception, representation, and analogy. *JETAI, 4*, 185–211. SME assumes the representation. **Why:** extraction, not matching, is the load-bearing risk.
7. Holyoak, K. J., & Thagard, P. (1989). Analogical mapping by constraint satisfaction. *Cognitive Science, 13*, 295–355. Pragmatic/goal constraints. **Why:** mapping is not context-free; fingerprints of a thought-without-goal overclaim.
8. Shervashidze, N., et al. (2011). Weisfeiler-Lehman graph kernels. *JMLR, 12*, 2539–2561. **Why:** cheap structural similarity ≠ analogical mapping.
9. Scetbon, M., Peyré, G., & Cuturi, M. (2021). Linear-time Gromov-Wasserstein distances. arXiv:2106.01128. GW NP-hard; entropic \(O(n^3)\). **Why:** FGW is not a 40-hour verifier.
10. van Noord, R., et al. (2023). A fair and in-depth evaluation of existing end-to-end entity linking systems. arXiv:2305.14937. ReFinED 73.3% F1; metonym errors ~31%. **Why:** Knowledge DNA on short labels is noisy overlap.
11. Uwasomba, C., Nnamoko, N., & Korkontzelos, Y. (2026). Deterministic and trustworthy LLM-driven semantic knowledge graph construction. ICCSC 2026. Raw extraction varies across runs; relations worse as temperature rises. **Why:** fingerprints of raw extracts fail self-match.
12. Resonance `WHY_NOT.md`. Embeddings collapse structure; LLM-as-judge unreproducible; no universal KG first. **Why:** keep these rejections; they do not imply a Shazam index.
