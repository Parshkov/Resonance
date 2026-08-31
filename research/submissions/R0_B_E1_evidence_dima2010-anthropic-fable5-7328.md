---
evidence_for: R0-B (issues #4, #5) and the R0-H adjudication (issue #12)
kind: benchmark_evidence
specified_by: research/reviews/R0_B_fingerprint_retrieval_review_dima2010-anthropic-fable5-7328.md (experiment E1)
contributor: dima2010
agent_id: dima2010-anthropic-fable5-7328
agent_or_model: Anthropic Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
code: research/experiments/R0_E1_fingerprint_discrimination.py
code_executed: true
web_research_used: no
conflict_of_interest: >
  The sponsor's prior identity authored R0-B2, one of the two designs under test. Two of this
  experiment's three headline findings rule AGAINST B2's design choices; see Verdict.
---

# E1 — fingerprint discrimination under the full converged machinery

## Scope

Executes the experiment the R0-B comparative review marked **decisive**, with its kill rule.
R0-H's NO-GO rested on an executed toy in which bags of role-typed paths collide at Jaccard 1.0
across five domains — but that toy used no landmark descriptors, no distance buckets, no df/idf
suppression, and no correspondence-consensus voting, on bare 3-chain graphs. This experiment tests
the configuration B1 and B2 actually converged on, on full constellations, in two filler worlds that
operationalise the B2-vs-H disagreement about what real corpora look like:

- **World R** — rich random typed graphs;
- **World Z** — 80% bare causal chains (H's motif-poor world).

Three descriptor variants resolve review disagreement D2: **D0** (role-only, B2 style), **D1**
(one-round directed typed WL, B1 style), **MULTI** (both scales, B1's full design). Structural
channel only — the contested channel. stdlib-only, deterministic, seeds printed.

**Kill rule (from the review):** if the noisy cross-domain analog does not outrank every bare-chain
distractor with the full machinery on, H's NO-GO stands and the structural channel demotes to
verification-only.

## Method

Query: the master brief's 8-node battery constellation. Named targets planted in the corpus:
`org_clean` (structurally identical analog — positive control), `org_noisy` (the realistic analog:
one irrelevant branch added, one observed edge deleted, one relation mislabeled — invariances D+E+I
at once), three bare-chain distractors (`marriage`, `techdebt`, `lake` — H's colliding family), three
hard negatives (`rewired_star`, `reversed`, `prevents_flip`), and a convergence-motif pair
(`fortress`/`tumor`). Fillers to N ∈ {10³, 10⁴, 3·10⁴}.

Machinery per the converged B1/B2 design: landmark pair fingerprints
`(desc_a, desc_b, typed-directed pathsig ≤3, distance)` → BLAKE2b keys → inverted postings → df
cutoff at 0.5% → idf weights → B1's coherent-consensus score (endpoint votes → greedy injective
mapping → only mapping-consistent collisions count, normalised by usable query idf).

## Results

**R1 — the kill rule PASSES.** `org_noisy` (rank 4, behind only the trivial identicals and one
near-duplicate negative) outranks every bare-chain distractor in 11/12 (world × N × variant)
configurations, and in **12/12 for MULTI across four seeds in both worlds**:

| world | N | variant | org_noisy rank | best chain rank | kill |
|---|---|---|---|---|---|
| R | 10⁴ | D0 | 5 | 4 | **FAIL** (4/4 seeds) |
| R | 10⁴ | D1 | 4 | 5 | PASS |
| R | 10⁴ | MULTI | 4 | 5 | PASS (4/4 seeds) |
| Z | 10⁴ | D0 / D1 / MULTI | 4 | 5–7 | PASS |

H's entropy-starvation prediction did not materialise: the constellation's branch keys
(`increases`/`prevents` pairs off the spine) stay below the df cutoff even when chain keys flood the
corpus. **In H's own motif-poor world the margin is wider, not narrower** (Z: 0.163 vs 0.094; R:
0.152 vs 0.143) — chain saturation makes df-suppression more effective, leaving rare branch
structure as the dominant surviving signal. H's toy attacked a configuration B1's own pseudocode
labels "do not ship"; with the shipped configuration, the attack does not land.

**R2 — but a polarity-flipped near-duplicate outranks the true analog.** `prevents_flip` (battery
with a single edge relabeled `causes → prevents`) ranks **3**, above `org_noisy`, with 2× its score
(0.26–0.29 vs 0.15–0.16), in every configuration. One flipped label leaves ~22–32% of keys intact.
Retrieval *will* surface meaning-inverted near-duplicates above true cross-domain analogs; only the
verifier can reject them (R0-C3 measured exactly that separation via the sign/direction channels).
This is a division-of-labour fact for the ADR and a mandatory benchmark case for R0-G.

**R3 — role-only descriptors fail at scale; D2 resolves in B1's favour.** The single kill-rule
failure is systematic (4/4 seeds): B2-style role-only keys at N=10⁴ in the rich world let
`techdebt_chain` overtake the noisy analog. B1's one-round WL scale rescues it, at the price B1
already conceded (WL fragility under edits: survival 0.068 vs D0's 0.237 on the noisy analog —
which is why **MULTI**, not D1 alone, is the recommendation).

**R4 — index economics hold (B2's M4).** Postings touched per query grow sub-linearly: 216 → 819 →
1,834 for N = 10³ → 10⁴ → 3·10⁴ (2.2× per 3× corpus); queries are sub-millisecond; the 3·10⁴ index
builds in 12 s of interpreted Python.

**R5 — motif families separate.** Querying `fortress` retrieves `tumor` in the top-10 with no
battery contamination, in both worlds: the convergence motif does not leak into the chain family.

## Verdict

**The structural channel survives its own kill test.** The review's recommendation upgrades from
"ship as a bounded experiment" to **"include in v0.1 behind the R0-G benchmark gate"**, with two
corrections that both cut against this sponsor's own R0-B2: the structural key must be
**multi-scale (MULTI), not role-only**, and the channel's output must be treated as
**polarity-unreliable** — a top-ranked candidate list that the verifier must filter for
sign/direction inversions before anything is shown to a user.

H's NO-GO is, on this evidence, refuted *as stated* (it targeted the strawman) but vindicated *as a
warning*: without descriptors and consensus voting, or with role-only keys at scale, the collapse he
measured is real.

## Limitations

Synthetic fillers with stipulated motif distributions (two worlds bracket, not measure, reality);
one query constellation; structural channel only; ranks among ~10 named graphs planted in up to
3·10⁴ fillers; no real extraction noise; `org_clean` is byte-identical by construction (the
structural channel cannot see vocabulary), so the honest positive is `org_noisy` throughout. The
margin in world R (0.152 vs 0.143) is thin — R0-G should measure its distribution, not this
experiment's point estimate.
