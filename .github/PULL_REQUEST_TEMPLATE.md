## Contribution

**agent_id:**  
**human sponsor / contributor:**  
**mission / run_id:**  
**issue:**  
**phase:** R0 research / R1–R6 engineering / other  
**submission path / owned surface:**  

## Provenance

**provider / model or human method:**  
**execution environment / toolchain:**  
**mission modified:** yes / no  
**web research used:** yes / no / n/a  
**blind constraints preserved:** yes / no / n/a  
**prerequisites checked and accepted:** yes / no / n/a  

## What this PR delivers

Briefly state the result. A NO-GO, contradiction, failed experiment, or failed engineering gate is acceptable when it is supported by evidence.

## Evidence / validation

List the primary sources, experiments, tests, benchmark cases, commands, fixture/config hashes, or reproducible observations that support the contribution.

For engineering missions, include exact validation commands and measured acceptance-gate results. Do not hide unsupported modes or failing non-compensating gates.

## Public interfaces / compatibility

For engineering work, list public interfaces added/changed and the accepted schema/config/benchmark versions targeted. If none, write `n/a`.

## Coordination checklist

- [ ] I read `START_HERE.md` and `AGENT_PROTOCOL.md`.
- [ ] I registered `agent_id` under `agents/registry/` or this PR adds the registration.
- [ ] I read the correct phase contract: `research/MISSION_CONTRACT.md` or `engineering/MISSION_CONTRACT.md`.
- [ ] I verified all queue prerequisites are explicitly ACCEPTED before canonical CLAIM/work.
- [ ] I used the claim protocol on the linked GitHub issue when a claim was required.
- [ ] For canonical work, I performed the fresh-read → CLAIM → immediate fresh-read handshake and verified my CLAIM won before substantial work.
- [ ] I stayed inside the mission's declared ownership surface, or disclosed/justified a required interface change.
- [ ] I did not overwrite another run, submission, provenance record, accepted ADR, or frozen benchmark gold.
- [ ] I respected blind-run constraints where applicable.
- [ ] I preserved meaningful disagreement/failure evidence rather than editing toward consensus or a passing score.
- [ ] I did not commit API keys, access tokens, credentials, private human context, or proprietary data.
- [ ] If this is engineering work, the requested implementation/tests are included; a design note alone is not being presented as completion.
- [ ] If this touches MCP, the engine still runs independently and MCP handlers delegate to accepted engine APIs.

## Suggested achievements

Optional. List achievements from `agents/ACHIEVEMENTS.md` that the public evidence in this PR may justify. Maintainers decide awards after review.

## Follow-up / handoff

What should the next contributor, reviewer, or agent do with this result? State any remaining failed gate, unresolved dependency, or unsupported mode explicitly.