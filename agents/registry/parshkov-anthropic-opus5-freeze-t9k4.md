---
agent_id: parshkov-anthropic-opus5-freeze-t9k4
human_sponsor: Parshkov
github_handle: Parshkov
provider: Anthropic
model: Claude Opus 5 (claude-opus-5)
model_mode: high-effort
execution_environment: Claude Code on the web (remote cloud container, Linux 6.18, Python 3.11, Chromium via Playwright, public network egress available)
first_seen: 2026-09-04
public_contact: none
---

# parshkov-anthropic-opus5-freeze-t9k4

## Capabilities used

- executing the repository gates (`unittest`, `benchmark/r0-v0.2`, `benchmark/extraction-v0.2`)
- direct HTTPS egress to the public production origin, so the stdlib acceptance
  scripts (`ops/hosted_onboarding_probe.py`, `ops/oauth_smoke.py`,
  `submission/evidence/abc_mcp_test.py`) run end to end against `/mcp`
- Resonance custom connector (`resonance_*` MCP tools) for the hosted-client card
- Railway MCP for deployments, variables and logs
- GitHub coordination writes (pull requests, issue comments)

## Public notes

Sponsor-assigned run: test the product on engine 0.2 end to end and bring the
repository to a new release freeze. Model identity is reported from the session
runtime (`configured_model` and `last_served_model` both `claude-opus-5`), not
inferred.

This run does not hold a canonical R0-R17 mission slot; it is explicitly
requested current-milestone verification and release work under
`work/CURRENT_MILESTONE.md` §"What to do when current product slots are occupied"
item 4.

## Contributions

Do not maintain this section speculatively. Add links only after a submission/PR exists.

- none yet
