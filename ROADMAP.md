# What's next

## The thing that decides everything

**Seven shared thoughts exist in the world.** That is the entire live corpus.

Everything below is secondary to that, and it is worth saying plainly because
the project has spent most of its effort on the other side. The engine now has
eighteen benchmark families, five verdicts, thirteen thresholds, four policy
versions and seven ADRs. The corpus has seven thoughts. A matcher with nobody
to match is not a product, however good the matching is — and the matching is
now good enough: on 2026-09-06 it found a genuine cross-domain twin between two
people who had never met.

There is an irony worth naming. The thought that produced that match was about
a registry of employer conduct, and its author had already reasoned out the
binding constraint: *while there are few reports there is no signal, so start
from those who already hold the data.* That is exactly Resonance's own
constraint, and it has never been applied to Resonance.

So the first question is not "is the engine right?" It is **"where do the first
few hundred thoughts come from?"** Some honest options, none of them code:
seed from a community that already writes down what it is working on; invite
people around one narrow problem rather than in general; or accept that the
standing search — "we will tell you when someone arrives" — is the whole
product until the pool is large enough for search to return anything.

Nothing below matters if that is not answered.

## What a person actually gets, today

Worth holding in view while reading the rest. A person shares a thought and,
almost always, hears that nobody matched yet. That is honest, and it is thin.
The parts that make it not-thin are the standing search and what is said when a
near miss turns up — not another decimal place on the classifier.

## Then: can the idea be falsified?

### 1. The embedding baseline

The one experiment this project set itself and never ran.
[`WHY_NOT.md`](WHY_NOT.md) rejects whole-thought embeddings, and
[ADR-0004](docs/decisions/ADR-0004-concept-aligned-analogy-and-benchmark-v0.2.md)
names "the lexicon channel adds nothing over whole-thought embeddings" as the
condition for reconsidering the architecture. Nobody has measured it.

Run a whole-thought embedding over the same Benchmark v0.2 pairs and report it
beside engine 0.2 — **per family**, because the question is not overall accuracy
but whether embeddings can do `cross_domain_analogy` while still rejecting
`template_coincidence` and `same_vocabulary_wrong_structure`. Keep the gate
split separate.

If the baseline matches the engine, the structural machinery is not earning its
complexity and that has to be said out loud. If it does not, this is the claim
the project has never been entitled to make.

### 2. Human review of the benchmark gold

Every gold label and every benchmark graph was authored by agents. Until a
person has reviewed the 8 analogy families and the 8 template-coincidence
negatives, `classification_accuracy = 1.0` means "no regression", not
"generalises", and no external claim should rest on it.

[ADR-0005](docs/decisions/ADR-0005-same-vocabulary-cross-domain-verdict.md) is
explicitly waiting on this and must not be settled by moving a threshold.

### 3. Real thoughts

Every graph measured so far is authored, not extracted from a real
conversation — and
[ADR-0006](docs/decisions/ADR-0006-label-encoder.md) recorded the lexicon
scoring 0.00–0.07 on real pairs, which is what the label encoder exists to fix.
A consented corpus of real extracted thoughts, with two-human gold, is the only
thing that measures the product as used.

### 4. Scale

Query time is linear from roughly 350 graphs upward — 148 ms at 176, 580 ms at
1408 — which is the second condition ADR-0004 names for reconsidering the
concept channel. `ResonanceEngine._require_bound()` additionally re-hashes the
whole corpus on every query. Not urgent at the current corpus size, and a wall
at 10⁴.

### 5. Multilingual prose extraction

`src/extraction/cue.py` is English-only — not just its cue table, but its
sentence splitting (it wants a capital Latin letter after the period), its
clause boundaries, and its noun-phrase heuristics. A conversation in another
language therefore yields an honest empty graph and the assistant must supply
the structure itself.

That is now a visible seam rather than a hidden one: the lexicon reads Latin
and Cyrillic, the optional encoder reads every script, and the tool contract
says the extractor is the English-only part. Closing it means a real extraction
mission per language, with its own gate, not more regular expressions.

## Smaller, known

- Make CI required in branch protection (a repository-settings action).
- The canonical origin and the Railway alias derive **different OAuth issuers**
  from the Host, so a client registered at one is audience-bound there; consider
  redirecting the alias.
- Cards B (claude.ai connector) and C (ChatGPT developer mode) have never been
  executed by a person.

---

The roadmap that ran during construction — R0 through R17, mission by mission —
is in [`history/ROADMAP.md`](history/ROADMAP.md).
