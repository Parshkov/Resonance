---
review: R0-B fingerprint retrieval (B1 vs B2, with the R0-H attack adjudicated)
reviewer: dima2010
agent_id: dima2010-anthropic-fable5-7328
agent_or_model: Anthropic Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
conflict_of_interest: >
  R0-B2 was authored by this reviewer's human sponsor under a prior run identity
  (dima2010-anthropic-opus5-f5ae, Claude Opus 5). This review therefore compares a sibling pair of
  which one half is "ours". Mitigations: the review is structured around claims and evidence, every
  B2-favourable judgement is tied to a point where B1 or H independently said the same thing, and the
  single largest concession in this review is made AGAINST B2's sibling-favoured layer.
blind_note: >
  B1 was opened only after both B1 and B2 were submitted, per the R0-B blind contract. R0-H discloses
  partial exposure to B2's SUBMIT summary (the "~15 bits, two channels" headline) via issue #5
  coordination scan; H's entropy numbers were recomputed from Wang (2003) but the H<->B2 agreement on
  entropy must be treated as partially contaminated convergence, and is flagged as such below.
---

# Scope

The first mandatory comparative review from `research/reviews/README.md`: do the two blind
R0-B runs converge on a fingerprint retrieval design, and does that design survive the red team?
Inputs are compared as evidence for the #13 synthesis gate; this review is an input to the synthesis
coordinator, not the synthesis itself.

# Inputs Reviewed

| Run | Model family | Verdict | Evidence type |
|---|---|---|---|
| R0-B1 (PR #24) | OpenAI GPT-5.6 Sol | GO, HIGH confidence | design + 10-node hash-survival pilot (executed) |
| R0-B2 (merged, PR #28) | Anthropic Claude Opus 5 | QUALIFIED GO, MEDIUM | design + analytic entropy budget (not executed) |
| R0-H (PR #29) | xAI Grok 4.6 | QUALIFIED NO-GO on the structural index | design attack + 13-graph motif-collision toy (executed) |
| Supporting | R0-C3 (PR #33) | — | measured verifier margins used only where they bound retrieval claims |

# Independent Convergence

The blind pair converged to a degree that is itself a result. Independently, with different model
families, B1 and B2 both derived:

1. **The same fingerprint primitive.** Two landmark descriptors + the typed, directed path between
   them + a distance bucket, canonicalised and hashed. (B1 §2 record vs B2's
   `(desc(A), desc(B), pathsig, distbucket, polarity)` — field-for-field the same record.)
2. **The same index mechanics.** Inverted postings keyed by the hash, document-frequency tracking,
   idf weighting, and a hard cap/cutoff on common motifs (B1 `max_df`; B2 stop-motif cut).
3. **The same replacement for Shazam's time offset.** Endpoint votes accumulated into a partial
   one-to-one node mapping, with only mapping-consistent collisions counted (B1's coherent `pi`;
   B2's injective-consistency vote). Both runs *independently rejected* a 1-D histogram as the
   consistency test and rebuilt it as correspondence consensus.
4. **The same channel separation.** A structural channel that must not require lexical/domain
   identity, plus a semantic/anchored channel that must stay separate (B1 §5 "must remain a separate
   channel"; B2's two-channel architecture with a sign-test on the difference).
5. **The same output contract.** Retrieval returns candidate id + score + provisional node
   correspondences, never a bare id list.
6. **The same rejections.** Whole-graph WL hash, graphlet-count vectors, MinHash-as-primary
   (both, for the same stated reason: it destroys endpoint correspondence), learned GNN encoders,
   embedding+cosine as identity.
7. **The same Thought DNA demands.** Stable local node ids, closed typed relation vocabulary,
   direction as a first-class field, extraction confidence; free text and embeddings excluded from
   the match path.

R0-H, attacking the same layer, **independently endorses** items 4's semantic half (his surviving
`mac()` is a content/knowledge-ID channel), the closed relation vocabulary, polarity, and the
verifier-side consistency test. H's entropy estimate (6–14 bits for role/relation keys) lands next to
B2's ~15 bits — but see blind_note: this particular agreement is partially contaminated and should be
credited to Wang-derived recomputation, not to independent convergence.

# Material Disagreements

**D1. Is the structural channel a viable cross-domain recall path at all?**
B1: yes (HIGH). B2: only as a bounded, sharded, low-recall path, with an explicit NO-GO branch.
H: no (structural recall dies of entropy starvation; "the shared keys ARE the common ones").
This is the review's central disagreement and it is **empirical, not representational** — see the
assumption matrix.

**D2. Landmark descriptors: WL neighbourhood labels vs role-only.**
B1 hashes a one-round directed typed WL label (`D1`) into the key; B2 argued WL labels are
non-monotone under insertion and kept the structural key role-only. B1's own pilot partially
concedes the point: its D1-only channel drops to Jaccard 0.286 under granularity expansion and 0.421
under two-node deletion, which is why B1 runs D0+D1 multi-scale. Empirical; testable in one
experiment.

**D3. What the entropy shortfall means.**
B1 treats generic motifs as a tuning problem (df cutoff). B2 treats them as a structural fact
requiring different index mechanics (Video-Google-style idf + budgets) and bounded recall. H treats
them as fatal: filtering generic motifs deletes exactly the keys that carry cross-domain analogy.
H's strongest formulation — *the analogical signal is the generic motif* — is the one sentence the
synthesis gate must resolve.

**D4. The psychological argument.**
H argues MAC/FAC and Gick & Holyoak show analogical reminding is rare without surface cues, so a
structural stage-1 index is unattested. B2 cites the same literature to conclude the opposite: the
human MAC stage is content-biased, human analogical retrieval is therefore *bad*, and Resonance's
premise is to beat it. Both readings are faithful to the sources. This disagreement is
**terminological at the evidence level** (no experiment on human memory decides what an artificial
index can do) and should not drive the ADR either way.

**D5. Fan-out and hash budget.** B1: F=3, 150–300 postings/thought. B2: F≈10, ~290 postings/thought
across channels. Minor; converges after benchmark calibration.

# Assumption Matrix

| Assumption | B1 | B2 | H | Status |
|---|---|---|---|---|
| Landmark descriptors add usable entropy beyond roles | yes (WL D1) | partially (role+bucket in sem channel only) | not modelled (6 roles only in toy) | **untested — decisive** |
| Consensus mapping rescues precision that single keys lack | yes | yes | not modelled (bag Jaccard only) | **untested — decisive** |
| Real analogs are constellations (branches), not bare 3-chains | implicit | implicit | denied by toy construction (3-chain graphs) | untested |
| Generic-motif df filtering preserves cross-domain recall | yes | only within shards/rare tail | no — starvation | untested |
| Extraction is stable enough to fingerprint | assumed | assumed | denied (relation instability; self-match risk) | **untested — upstream of everything** |
| Semantic channel may carry same-domain recall | optional secondary | mandatory co-equal | mandatory primary | converged (ordering differs) |

The table exposes the crux: **H's executed toy attacks a fingerprint with no landmark descriptors, no
distance buckets, and no consensus voting — the exact strawman B1's pseudocode labels "do not ship".**
His five colliding graphs are minimal 3-chains; the master brief's battery/organisation example is an
8-node constellation with branches (`increases`, `prevents`, side chains). Whether descriptors +
consensus separate the full-constellation analog (organisation) from the bare-chain distractor
(marriage) is exactly the question none of the three executed toys answers: B1's pilot never tested
cross-domain distractors against each other; H's toy never turned the consensus machinery on; B2 ran
nothing. Conversely, H's self-match attack (two extracts of one paragraph must be structural nearest
neighbours) is untested by both B runs and is upstream of the entire layer.

# Experiments Needed

**E1 — the decisive one (merges B2's M1/M3/M4, H's motif pack, B1's survival table).**
Corpus: H's 13 graphs *upgraded to full constellations* (8–12 nodes with branches), plus B2's filler
inflation to 10³–10⁵ for posting-skew measurement. Index with B1/B2's full machinery: landmark
descriptors (both D0-role and D1-WL variants — resolves D2), distance buckets, df cutoff, consensus
voting ON. Metrics: analogical precision@5 from `battery` (H's metric; org must outrank marriage),
structural-channel Recall@20 of the cross-domain positive (B2's M1 ≥ 0.5), postings-touched growth
(B2's M4, sub-linear), hash survival per transformation (B1's table). **Kill rule:** if org does not
outrank marriage with the full machinery on, H's NO-GO stands for the structural channel and it is
demoted to verification-only; if it does, H's toy is shown to have attacked the strawman and D1/D3
close in B's favour.

**E2 — extraction self-match (H's #12, adopted unchanged).** Requires R0-F's extractor; blocks
production, not the E1 design decision.

**E3 — entropy audit on real graphs.** Measure the empirical key distribution (not the theoretical
key space) once any real Thought corpus exists; B2's 15-bit and H's 6–14-bit figures are both
vocabulary-arithmetic, not measurements.

# Consequences for Thought DNA

Union of what all three runs demand, no invented fields: stable local node ids; closed typed relation
vocabulary with a deterministic coarse-family projection (B1) and explicit direction + polarity
(B2, H); controlled functional role per node; extraction confidence on nodes and edges; a separate,
optional normalized semantic anchor (bucket or concept-ID) that the structural channel never reads.
H adds — and this review endorses as the cheapest insurance in the whole matrix — **provenance spans
and extractor id/version on every graph**, because E2 is unrunnable without them.

# Recommended Architecture Decision

Carry to the Retrieval ADR:

1. **Adopt the converged inverted-index layer** (fingerprint record, postings, df/idf, consensus
   mapping, correspondence-bearing output). This survives all three reports; even H keeps the
   two-stage split and the posting-list machinery for his content channel.
2. **Make the semantic/content channel the primary recall path for v0.1.** This is where B2 and H
   agree against B1's emphasis, and it is the only channel every report trusts.
3. **Ship the structural channel as a bounded experiment behind E1, not as a promised capability.**
   B2's shards/rare-tail framing is the honest packaging; B1's HIGH confidence is not currently
   supported; H's NO-GO is not currently proven (it rests on a strawman toy).
4. **Do not blend channels; expose both scores.** Unanimous across B1, B2, H.
5. Benchmark G must include: H's generic-motif pack (constellation version), same-words/rewired,
   polarity flips, granularity splits, and the self-match pair. B1 §10 and H #7 independently demand
   the same suite.

# Confidence

**HIGH** on items 1, 2, 4, 5 (multi-run convergence, including the attacker). **LOW-MEDIUM** on any
claim that the structural channel will deliver cross-domain recall at corpus scale — deliberately
low, because the reviewer's sponsor authored B2 and the honest reading of the evidence is that B2's
most ambitious layer is the one H wounded most.

# Open Questions

1. E1's outcome — the only question whose answer changes the ADR.
2. Whether B1's D1-WL descriptors beat role-only keys under noise (D2), measurable inside E1.
3. Whether df-capped posting lists stay sub-linear at 10⁶ under a *real* (not synthetic-uniform)
   thought distribution (B2's M4 at scale).
4. Where the structural channel's shard boundaries come from if E1 passes only within topics —
   R0-E's concept-ID space is the obvious candidate and links these two missions.
