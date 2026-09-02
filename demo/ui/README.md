# R9 visual client

This is the competition-recordable Resonance discovery surface. It is an
offline-first presentation client over the accepted
`resonance-discovery/0.1` response. The browser does not match, retrieve,
rerank, verify, threshold, or calculate scores.

## Launch

From the repository root, with Python 3.10 or newer:

```bash
# Deterministic capture from the genuine accepted R8 fixture
python3 -m demo.ui.serve --source replay

# Accepted R8 discover_resonance MCP call, then the same renderer
python3 -m demo.ui.serve --source live
```

Open <http://127.0.0.1:8765/>. Both modes remain switchable in the header.
The request is pinned in both paths to:

```text
mode=analogical
k=15
```

REPLAY returns
`src/discovery/fixtures/example_response.json` byte-for-byte. LIVE starts the
accepted `src.discovery.demo_server`, performs MCP `initialize`, calls
`discover_resonance`, and renders its accepted DTO through the same frontend.
Verify the two paths without opening a browser:

```bash
python3 -m demo.ui.serve --verify-sources
```

The expected flagship session order is:

1. `ses-gabe-warehouse`
2. `ses-kwame-traffic`
3. `ses-mei-battery-heat`
4. `ses-noah-org-overload`

The frontend selects the first four discoverable, non-hard-rejected
`analogical` rows by iteration. It never sorts them. All other returned rows
remain accessible in the secondary drawer, while hard rejections appear only
as contradictions.

## Record at 1920×1080

1. Run `python3 -m demo.ui.serve --source replay`.
2. Set the browser viewport to exactly 1920×1080 at 100% zoom.
3. Open `http://127.0.0.1:8765/?source=replay`.
4. Wait until the footer reads `REPLAY · genuine accepted R8 fixture · analogical / k=15`.
5. Record or capture the viewport; no page scrolling is required.

The inspected reference frame is
[`artifacts/canonical-1920x1080.jpg`](artifacts/canonical-1920x1080.jpg).
Its dimensions are asserted by the UI test suite.

## Privacy and boundaries

- Only rows with `display.share_state=discoverable` can render.
- Missing location stays missing; Gabe is shown as `Location not shared`.
- Locations are coarse/synthetic map decoration and never affect ordering.
- Hard rejections are segregated into the rust contradiction treatment.
- No contact details are requested or rendered.
- Introductions are explicitly unavailable because `request_intro` is not an
  accepted R8 MCP tool.
- The UI imports no engine, alignment, retrieval, verifier, fingerprint, index,
  or scoring internals.

The server uses only the Python standard library. The browser uses native HTML,
CSS, JavaScript modules, and deterministic inline SVG. There is no build step,
package-manager dependency, web font, map tile, analytics call, or remote
runtime asset.

## Validation

```bash
python3 -m unittest tests.test_demo_ui -v
python3 -m unittest discover -s tests
git diff --check
```

Design and implementation provenance is recorded in
[`PROVENANCE.md`](PROVENANCE.md) and
[`../../.superdesign/design-system.md`](../../.superdesign/design-system.md).
