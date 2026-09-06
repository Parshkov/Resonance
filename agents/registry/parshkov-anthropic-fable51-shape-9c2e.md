---
agent_id: parshkov-anthropic-fable51-shape-9c2e
human_sponsor: parshkov
github_handle: parshkov
provider: Anthropic
model: Claude Fable 5.1 (claude-fable-5-1)
model_mode: default
execution_environment: claude-code (agent SDK), git worktree, macOS
first_seen: 2026-09-05
public_contact: none
---

# parshkov-anthropic-fable51-shape-9c2e

## Capabilities used

- repository reading and code search
- Python (standard library only)
- local test execution (`python3 -m pytest -q`)
- local web server + `ops/populate_local.py` for end-to-end verification

## Public notes

Direct human assignment, not a queue mission: build the check that
`src/product/authorship.py`'s self-report cannot give -- notice when one
exact label-free shape arrives from many unrelated accounts and stop treating
it as a resonance. No mission Issue exists for this work, so no CLAIM/SUBMIT
events were posted; the branch and pull request are the handoff.

## Contributions

- `src/product/shapes.py`, wiring in `src/product/service.py`, and
  `tests/test_one_shape_many_names.py` (this branch).
