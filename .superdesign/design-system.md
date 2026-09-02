# Resonance R9 Visual Discovery — Design System

## Product and audience

Resonance is a privacy-aware thought-discovery system. This R9 surface is a
single-screen, competition-video-ready visualization over the accepted R8
discovery contract. It is used by a person exploring their active thought and
by judges who need to understand the flow immediately: consent is shared,
discovery runs against an offline map, useful structural resonances appear in
backend order, and a selected match explains why it resonates.

This interface is a visual client only. It never matches, reranks, recalculates
scores, applies thresholds, or imports discovery internals. Every displayed
value comes from the discovery response. Live and replay modes render through
the same response path.

## Visual direction: scientific neural noir

The mood is a calm scientific observatory rather than a consumer social feed.
Use a near-black graphite canvas (`#0a0a0a`) with a subtle dot grid, low-opacity
glass panels, restrained bronze/gold resonance accents, and generous negative
space. The result should feel precise, private, and quietly alive.

Do not use blue or purple gradients. Avoid generic dashboard chrome, large
marketing headlines, excessive pills, neon cyberpunk effects, or ornamental
data that is not in the fixture.

### Color tokens

- Canvas: `#0a0a0a`
- Raised canvas: `#10100f`
- Glass panel: `rgba(255, 255, 255, 0.035)`
- Glass border: `rgba(255, 255, 255, 0.10)`
- Primary text: `#f2eee8`
- Secondary text: `#aaa49b`
- Muted text: `#8b857d`
- Resonance bronze: `#a78b71`
- Resonance gold: `#c9b8a0`
- Bright connection: `#e8d5b7`
- Consent/live sage: `#94a890`
- Contradiction rust: `#b66d58`
- Focus ring: `#e8d5b7`

Gold indicates structural resonance and selection. Sage indicates a safe,
available, or live state. Rust is reserved for contradiction evidence. Never
use color as the only signal.

### Typography

The interface must work fully offline. Use no remote font imports.

- Display and thought title: `ui-serif, Georgia, Cambria, "Times New Roman", serif`
- Interface and data: `Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Numeric and technical values: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`

Display text is sentence case. Small navigation labels use 10–12px uppercase
with 0.10–0.16em tracking. Body copy is 13–15px with comfortable line height.
Use tabular numerals for scores and counts.

## 16:9 composition

Design at 1920×1080 and remain usable down to 1280px wide. The entire primary
story must be legible in a single frame without browser scrolling.

- Top status rail: 64px high. Resonance wordmark at left; `Consent shared`,
  corpus snapshot shorthand, and an explicit `Replay fixture` / `Live MCP`
  mode control at right.
- Left thought column: about 390px. Show the active thought, a compact causal
  chain, declared topic/domain context, and a small discovery summary. This is
  the stable narrative anchor.
- Center discovery field: flexible, at least 760px. Render an offline SVG map
  or semantic field with coarse synthetic points, one central thought node,
  illuminated useful-match nodes, dim additional result nodes, and a separate
  rust contradiction rail. The map must not imply geographic precision.
- Right matches column: about 450px. Show exactly the first four useful,
  non-hard-rejected matches in backend order as compact cards. The selected
  match is visually connected to the map.
- Detail surface: an integrated bottom sheet or inner overlay spanning the
  lower center/right, not a new route. It may replace part of the map while
  open, but it must preserve the thought and ordered match context.

Use an 8px spacing base. Primary panels use 24–32px internal padding, 24–32px
outer gutters, and 24–40px radii. Cards use 18–24px radii. Borders are hairline
and quiet; shadows are diffuse, never heavy.

## Canonical content for the design draft

Use the accepted replay fixture exactly as the design's data source. Do not
invent people, scores, locations, or system facts.

Active thought: `Plasma lens heat → ionization cascade → beam wander`, with an
aperture budget and adaptive cooling context. Discovery mode is `analogical`
and requested result count is `k=15`.

The first four eligible analogical matches, in backend order, are:

1. Gabe S. — `Inbound staging pile-up` — analogical — structural score `0.8875`
   — logistics — plasma lens heat ↔ inbound surge. No location is available;
   do not fabricate one.
2. Kwame A. — `Peak-hour spillback` — analogical — structural score `0.8875`
   — Nairobi · East Africa — plasma lens heat ↔ peak inflow.
3. Mei L. — `Cell heat degradation` — analogical — structural score `0.8875`
   — Austin · Texas — plasma lens heat ↔ cell heat.
4. Noah R. — `Inbox overload cascade` — analogical — structural score `0.8875`
   — Berlin · Central Europe — plasma lens heat ↔ inbox overload.

The selected default is Gabe S. Show that the verdict is `provisional`, and
make room in the detail surface for exact top correspondences and preserved
relations. Values can be formatted for readability but never normalized or
recomputed.

Show additional backend results as a quiet aggregate such as `9 other backend results`
only when that count is derived from the response. Show hard-rejected negative
results separately as contradiction evidence, never mixed into the useful
match order. A suitable fixture example is Lea V., `Causal inversion of heat
cascade`, with hard rejection `relation_type:r0->r0`; keep that technical value
secondary and rust-colored.

## Components and states

### Status rail

The mode must always be visible. Replay should read `Replay fixture` and may
show a small deterministic/offline descriptor. Live should read `Live MCP`.
Both modes lead to the same rendering state. Do not imply live connectivity
while replay is selected.

Consent is visible as `Consent shared` with a text label and sage indicator.
The corpus snapshot may be shown as a short monospace fingerprint with an
accessible full-value affordance.

### Thought summary

Use a compact causal-chain visualization with arrows and restrained gold
highlights. Make `Active thought` explicit. Avoid editable controls in the
video-ready default state.

### Discovery map

Use deterministic SVG/CSS only—no remote map tiles, chart libraries, or random
positions. Curved hairline links can breathe with a subtle opacity pulse, but
node placement and every screenshot must be deterministic. Useful matches use
gold rings and numeric order labels. Other results stay dim. Contradictions sit
on a separate visual lane with rust dashed links.

### Match cards

Cards preserve response order, numbered 01–04. Each card includes person,
topic, match kind, exact structural score, and only available location. A card
click or keyboard activation selects it and opens its explanation. Do not sort
by score or add frontend confidence tiers.

### Match detail

Show selected identity/topic, match kind, exact score, verdict, node and
relation counts, top correspondences, and preserved relations directly from
the response. Use a two-column mapping treatment with a central connecting
line when space allows. The detail should explain structural analogy in plain
language while keeping canonical technical values visible.

`request_intro` is not exposed by the accepted R8 MCP surface. Do not render an
active request button or fake the capability. Prefer a quiet disabled line,
`Introductions are not available in this build`, or omit the action entirely.

## Motion and interaction

- Initial reveal: panels fade/translate 8px over 300–500ms with light stagger.
- Selected connection: slow 2.4–3.2s opacity pulse; no moving particles.
- Card hover/focus: 1px border brightening and 2px lift, 160ms ease-out.
- Detail transition: 240–320ms ease-out.
- Respect `prefers-reduced-motion`; remove movement while retaining selection.
- All controls must be keyboard reachable, visibly focused, and at least 40px
  high. Use semantic buttons, headings, and status text.

## Fidelity and implementation guardrails

Use only the fonts, colors, spacing, radii, composition, motion, and components
defined above. Produce one coherent desktop screen, not a landing page or a
collection of alternatives. All assets must be local or code-native. The final
implementation must launch with documented commands, replay the accepted R8
fixture, support the live adapter without a separate renderer, and include a
deterministic 1920×1080 screenshot artifact.
