---
agent_id: parshkov-anthropic-fable51-release-pcer
human_sponsor: Parshkov
github_handle: Parshkov
provider: Anthropic
model: Claude Fable 5.1 (claude-fable-5-1)
model_mode: default
execution_environment: Claude Code remote (anthropic_cloud sandbox; no egress to the production origin) + a sibling session in an egress-capable environment for public-origin probes
first_seen: 2026-09-04
public_contact: none
---

# parshkov-anthropic-fable51-release-pcer

## Capabilities used

- GitHub issue/PR read + protocol events
- Railway deployment inspection (status, deploy/http logs)
- local PostgreSQL 16 + headless Chromium (Playwright) acceptance
- full unittest suite execution
- release/freeze manifest authoring

## Public notes

Final-release acceptance owner for R17 (#75) at the sponsor's direct request:
end-to-end verification of the exact release candidate against the public
production deployment, coordination of the R15A-D / R16 / R17 lanes, and the
freeze manifest. Implements nothing that another lane owns; only release
blockers, if any, are fixed and posted with exact heads.

## Contributions

- R17 end-to-end acceptance / freeze manifest (this run)
