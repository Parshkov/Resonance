---
agent_id: parshkov-anthropic-fable51-geo-0332
human_sponsor: Parshkov
github_handle: Parshkov
provider: Anthropic
model: Claude Fable 5.1 (claude-fable-5-1)
model_mode: default effort, Claude Code subagent in a git worktree
execution_environment: Claude Code (macOS, Python 3, Node 24 for module tests); local product server on 127.0.0.1 for verification
first_seen: 2026-09-05
public_contact: via GitHub @Parshkov
---

# parshkov-anthropic-fable51-geo-0332

## Capabilities used

- repository reading, local execution of the product server and the test suite
- code changes in the product web server and the browser interface; tests

## Public notes

Assigned directly by the sponsor: the geographic view of consented match
locations on the site, beside the structural resonance map. Owned surfaces:
`demo/ui/geo.mjs`, `demo/ui/geo.css`, new routes in
`src/product/web_server.py`, new tests.

## Contributions

- The geographic panel (`/api/geo`, `geo.mjs`, `geo.css`) and the fix that lets
  a browser share carry the coarse location it was given.
