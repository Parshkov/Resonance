# Contribute a consented demo session

This file is the public path for adding a later volunteer session. The seeded
v0.1 corpus is synthetic or manually curated; it does not contain private
human context.

## Rules

1. Share only a **Thought DNA** document plus the session envelope below.
   Raw chat logs are not required and should not be committed.
2. Use `record_provenance.record_kind = "volunteer"`.
3. Pseudonymous `person_id` / `display_label` only. No email, phone, legal
   name, or account handle.
4. Location, if any, must be `kind: synthetic_coarse`, `precision: city`,
   and rounded to 0.1 degree. Do not contribute a home or workplace pin.
5. Set consent flags explicitly. A session with `share_thought_dna: false`
   is stored but never discovered.
6. Domain/topic/cluster labels are presentation-only. Do not expect them to
   affect matching.
7. Thought DNA must validate as `thought-dna/0.1` with
   `provenance.kind = "manual"`.

## Envelope

```json
{
  "schema_version": "resonance-demo-corpus/0.1",
  "session_id": "ses-your-stable-slug",
  "person": {
    "person_id": "person-your-stable-slug",
    "display_label": "Public initials or chosen label",
    "avatar_placeholder": "your-stable-slug"
  },
  "consent": {
    "share_enabled": true,
    "share_thought_dna": true,
    "share_coarse_location": true,
    "share_display_profile": true
  },
  "location": {
    "kind": "synthetic_coarse",
    "region": "Named region",
    "city": "Named city",
    "lat": 0.0,
    "lon": 0.0,
    "precision": "city"
  },
  "presentation": {
    "domain": "short domain label",
    "topic": "short topic label",
    "cluster_id": "volunteer"
  },
  "record_provenance": {
    "record_kind": "volunteer",
    "builder_id": "your-agent-or-handle",
    "notes": "why this session is useful for the demo"
  },
  "thought_dna": {}
}
```

Open a PR that adds the record to a new line of `sessions.jsonl` **or**
extends `demo/corpus/build.py` and rebuilds. Run
`python3 -m unittest tests.test_demo_corpus -v` before submitting.
Do not edit frozen benchmark gold.
