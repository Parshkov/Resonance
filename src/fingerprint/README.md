# Relational fingerprints

This package derives disposable retrieval features from canonical Thought DNA
v0.1. It never writes fingerprints back into a `ThoughtGraph`.

The shipping policy is MULTI:

- D0 is the closed functional node role.
- D1 is one round of directed, relation-typed neighborhood refinement.
- landmark pairs are connected by every simple typed/directed path of length at
  most three;
- the path length is part of the feature key; and
- labels, node IDs, relation IDs, source order, and benchmark IDs are absent
  from structural keys.

Every equal path is retained. The implementation does not pick a shortest path
by relation-ID ordering, so relation renaming cannot change the feature set.
Role-only D0 can be constructed only as an explicitly labelled non-shipping
ablation.

`FingerprintConfig.feature_version` and `config_hash` identify the exact
derived-feature policy used by the index.
