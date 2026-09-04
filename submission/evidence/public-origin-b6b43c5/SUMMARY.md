# R9 empty/error state on the public origin @ `b6b43c5`

- **Commit under test:** `b6b43c55f18c4ac401a79563e9a821cea7483b44` (`main`, squash of #167 on top of the freeze commits)
- **Origin:** https://resonance-production-cfe3.up.railway.app
- **Railway deployment:** `d0bcb188-4124-40a0-b36b-78f7bcac990d` (auto-deploy from `main`)
- **Method:** `submission/evidence/r9_empty_state_harness.py` driving the **live** page in Chromium 141. The discovery response is stubbed at the network layer with the accepted R8 fixture mutated so every returned candidate is refused as a resonance — the shape observed on production at `0aea577`. The real deployed `app.mjs` renders it; nothing here talks to the engine.

## Result: 16/16

Against the recorded baseline (`summary='10 matches · 5 rejected'`, `kicker='WHY KWAME A. RESONATES'`, 4 mapping rows, 11 drawer rows):

| state | what the page now shows |
|---|---|
| discovery returns candidates, none clear the bar | `data-state="empty"`; 0 match cards; summary **`10 returned · 0 resonances · 5 rejected`**; kicker `NO RESONANCE IN THIS CORPUS`; heading `Nothing cleared the resonance bar`; 0 stale mapping rows; 0 stale relation chips; map status `0 resonances · every returned candidate was refused`; **15 drawer rows still inspectable** |
| injected HTTP 500 | `data-state="error"` and `{"cards":0,"mappings":0,"chips":0,"drawer":0,"markers":0,"connections":0,"summary":"—","kicker":"Evidence","contradictionHidden":true}` |

No uncaught JavaScript exceptions. Console *resource* errors are expected and excluded by name: the injected 500, and `/api/context?source=live` where the page is served without a live backend.

## What this closes

The freeze recorded an open R9 item: a person could read "10 matches · 5 rejected" over an **empty** primary rail, beside another source's named evidence and its mapping rows. The empty rail itself was always correct — `selectPrimaryMatches()` drops every `negative` match by design, refusing to advertise a false analogy. What was wrong was that the correct answer travelled through the error path, and that path cleared only the match list.

`selectPrimaryMatches()` is unchanged; no threshold, ranking or scoring was touched.

## Still open

`submission/evidence/browser_harness.py` asserts `cards > 0` after a LIVE discover. With the empty state now a first-class correct outcome, the precise assertion is `cards > 0` **iff** the payload holds at least one discoverable non-`negative` match. Card A therefore still reports 16/18 with that one check red against a corpus that legitimately holds no resonance for the page's own thought. Deliberately not changed inside the freeze, so that no acceptance assertion is relaxed.
