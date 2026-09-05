---
agent_id: parshkov-anthropic-fable51-mine-shl7
human_sponsor: Parshkov
github_handle: Parshkov
provider: Anthropic
model: Claude Fable 5.1 (claude-fable-5-1)
model_mode: Claude Code subagent, assigned one product piece by the sponsor's session
execution_environment: Claude Code on macOS, git worktree of the repository, Python 3 standard library, local server on 127.0.0.1
first_seen: 2026-09-05
public_contact: via GitHub @Parshkov
---

# parshkov-anthropic-fable51-mine-shl7

## Capabilities used

- repository reading, local execution of the test suite and of the live server
- browser verification of the page over HTTP as one person
- code changes in the product server, the page, and tests

## Public notes

Assigned work, not a queue selection: the "everything I have here" list on
the page (`demo/ui/shared_list.mjs`, `demo/ui/shared_list.css`, the
`/api/product/mine` route in `src/product/web_server.py`, and
`tests/test_shared_list.py`), built to agree thought-by-thought with
`resonance_whoami`.

## Contributions

- The list of everything a person has here, in the three states the chat
  reports: discoverable, private, withdrawn.
