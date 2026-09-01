# R9 visual demo

Competition recording client over accepted `resonance-discovery/0.1`.
This directory is a presentation surface. It does not implement matching.

## Run

From the repository root, Python ≥ 3.10, no extra packages:

```bash
python3 -m demo.ui.serve
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Replay is the canonical
offline path: it projects `src/discovery/fixtures/example_response.json`.

Live MCP path (same UI, `python3 -m src.discovery.demo_server` under the hood):

```bash
python3 -m demo.ui.serve --live
```

Or keep the replay server and open `/api/live` via `?source=live`.

Dump the projected view without a browser:

```bash
python3 -m demo.ui.serve --dump-view /tmp/r9-view.json
```

## Canonical recording

1. `python3 -m demo.ui.serve`
2. Open the page in a browser.
3. Record the `.stage` frame at **1920×1080**.
4. Click a match card to reveal backend correspondences.
5. Do not press Request intro — it is intentionally disabled. R8 v0.1 did not
   expose `request_intro` as an MCP tool.

Pinned query: Aria K. / `thought-aria-plasma-lens` / `mode=analogical` / `k=15`.

Highlighted cards use one explicit rule: the first four backend `matches[]`
rows whose `mode_classification` is `analogical` and `hard_rejection` is
null, preserving engine order. Other rows remain listed. Rejected rows stay
in the contradiction list.

## Visual regression

`demo/ui/fixtures/canonical_poster.svg` is a deterministic 1920×1080 poster
generated from the same view-model. Tests fail if the poster drifts.

## Dependencies

None beyond the repository and Python’s standard library.
