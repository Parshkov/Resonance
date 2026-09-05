/**
 * The page's own view of a discovery result: your thought, the people whose
 * reasoning has the same shape, the Resonance map of them, and the evidence
 * for the one you selected.
 *
 * Nothing here matches, ranks, rescores or sorts. Every number on screen is a
 * number the engine returned, and every order is the engine's order. This
 * module has no imports so the replay demo (demo/ui/server.py) can serve it
 * alone; the live modules talk to it through DOM events.
 */

const DISCOVERY_CONTRACT = "resonance-discovery/0.1";
const CONTEXT_CONTRACT = "resonance-ui-context/0.1";
const CANONICAL_MODE = "analogical";
const CANONICAL_K = 15;
const PRIMARY_CLASSIFICATION = "analogical";
const NEGATIVE_CLASSIFICATION = "negative";
const PRIMARY_LIMIT = 4;
const SHARE_REQUIRED = "share_required";
const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
  context: null,
  payload: null,
  primary: [],
  selectedSessionId: null,
};

function assertAcceptedContext(context) {
  if (context?.contract_version !== CONTEXT_CONTRACT) {
    throw new Error("Unsupported presentation context");
  }
  if (!context.consent?.shared_with_resonance) {
    throw new Error("This thought has not been shared with Resonance");
  }
  if (context.pinned_request?.mode !== CANONICAL_MODE || context.pinned_request?.k !== CANONICAL_K) {
    throw new Error("Presentation request is not pinned to analogical / k=15");
  }
}

function assertAcceptedDiscovery(payload) {
  if (payload?.contract_version !== DISCOVERY_CONTRACT) {
    throw new Error("Unsupported discovery response contract");
  }
  if (payload.query?.mode !== CANONICAL_MODE) {
    throw new Error("Discovery response is not analogical mode");
  }
  if (!Array.isArray(payload.matches) || !Array.isArray(payload.rejected)) {
    throw new Error("Discovery response is incomplete");
  }
}

function isDiscoverable(row) {
  return row?.display?.share_state === "discoverable";
}

export function selectPrimaryMatches(payload) {
  assertAcceptedDiscovery(payload);
  // Analogical resonances first (the R9 rule). A live person's thought may
  // resonate only directly or approximately; those are resonances too, so
  // remaining slots take the next eligible non-negative matches in backend
  // order instead of rendering nothing. Never sorted, never rescored.
  const eligible = payload.matches.filter((match) =>
    isDiscoverable(match) && match.hard_rejection === null &&
    match.mode_classification !== NEGATIVE_CLASSIFICATION);
  const selected = eligible.filter((match) => match.mode_classification === PRIMARY_CLASSIFICATION)
    .slice(0, PRIMARY_LIMIT);
  for (const match of eligible) {
    if (selected.length >= PRIMARY_LIMIT) break;
    if (!selected.includes(match)) selected.push(match);
  }
  return selected;
}

export function visibleOtherMatches(payload, primary) {
  const primaryIds = new Set(primary.map((match) => match.session_id));
  return payload.matches.filter((match) =>
    isDiscoverable(match) && match.hard_rejection === null && !primaryIds.has(match.session_id)
  );
}

export function visibleRejected(payload) {
  const rows = [...payload.rejected, ...payload.matches.filter((match) => match.hard_rejection !== null)];
  const seen = new Set();
  return rows.filter((row) => {
    if (!isDiscoverable(row) || row.hard_rejection === null || seen.has(row.session_id)) return false;
    seen.add(row.session_id);
    return true;
  });
}

// ---- backend order ------------------------------------------------------
//
// Every number shown next to a match is its position in the engine's returned
// list: `01`…`NN` for `matches[]`, `R1`…`RN` for `rejected[]`. The page never
// renumbers, so the order is recoverable from any surface.
function backendPosition(payload, row) {
  const matchIndex = payload.matches.indexOf(row);
  if (matchIndex >= 0) return String(matchIndex + 1).padStart(2, "0");
  const rejectedIndex = payload.rejected.indexOf(row);
  if (rejectedIndex >= 0) return `R${rejectedIndex + 1}`;
  return "—";
}

// ---- structural map layout --------------------------------------------
//
// The map is a view of numbers the engine returned, nothing more:
//   distance from centre = 1 − scores.structural   (inner ring 1.0, rim 0)
//   sector               = display.cluster_id     (in order of first appearance)
//   angle inside sector  = backend order
//   line weight          = evidence.preserved_relation_count
//   dashed               = evidence.contradiction_count > 0, or a hard rejection
const INNER_RADIUS_RATIO = 0.46;
const SECTOR_GAP_DEG = 10;

function clamp01(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(1, Math.max(0, number));
}

export function structuralRadius(structural, radiusMax, radiusMin) {
  return radiusMin + (radiusMax - radiusMin) * (1 - clamp01(structural));
}

export function layoutMap(items, geometry) {
  const {cx, cy, R} = geometry;
  const r0 = R * INNER_RADIUS_RATIO;
  const sectors = new Map();
  for (const item of items) {
    const key = item.cluster || "unclustered";
    if (!sectors.has(key)) sectors.set(key, []);
    sectors.get(key).push(item);
  }
  const sectorCount = sectors.size;
  const usable = 360 - SECTOR_GAP_DEG * sectorCount;
  const total = items.length || 1;
  const placed = [];
  const sectorArcs = [];
  let angle = -90;
  for (const [cluster, members] of sectors) {
    const span = sectorCount === 1 ? 360 : usable * (members.length / total);
    const start = angle;
    members.forEach((item, index) => {
      const theta = ((start + span * ((index + 0.5) / members.length)) * Math.PI) / 180;
      const radius = structuralRadius(item.structural, R, r0);
      placed.push({
        ...item,
        x: cx + radius * Math.cos(theta),
        y: cy + radius * Math.sin(theta),
        angle: theta,
      });
    });
    sectorArcs.push({cluster, start, end: start + span, count: members.length});
    angle = start + span + SECTOR_GAP_DEG;
  }
  return {placed, sectorArcs, r0};
}

function el(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgEl(tagName, attributes = {}) {
  const node = document.createElementNS(SVG_NS, tagName);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function setShellState(value) {
  const shell = document.getElementById("app-shell");
  if (shell) shell.dataset.state = value;
}

// Two decimals. Four is engineering precision that changes nothing a person
// can act on, and 0.8306 next to a pseudonym reads as machine output rather
// than as "these two are close". The exact number stays in the API.
// The engine's own words for how two thoughts relate. They are precise and
// they belong in the API, but "negative" printed beside a person's name reads
// as a verdict on THEM, and "analogical" is not a word a stranger arrives
// knowing. Say what each one means.
const CLASSIFICATION_IN_WORDS = {
  analogical: "same shape, different subject",
  approximate: "close — some of it lines up",
  literal: "the same thing, said the same way",
  negative: "not called a resonance",
};

function classificationInWords(value) {
  return CLASSIFICATION_IN_WORDS[String(value || "").toLowerCase()] || String(value || "");
}

// Cluster names arrive as slugs, because that is what they are inside the
// engine: "retry-storms-after-a-partial-outage", and in the seeded corpus
// even "unrelated-distractor". Nobody outside this repository should have to
// read a slug off a map legend.
function clusterInWords(value) {
  return String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/^\s*(.)/, (_, first) => first.toUpperCase())
    .trim();
}

function formatScore(value) {
  return Number(value).toFixed(2);
}

// The engine states a hard rejection as "direction:r_43c1...->r2" or
// "relation_type:...". That is a diagnostic, and it was printed to people in
// a <code> box: an identifier they cannot look up, about a decision nobody
// explained. Both kinds say something plain, so say it.
function rejectionInWords(reason) {
  const kind = String(reason || "").split(":")[0];
  if (kind === "direction") return "the same link, running the opposite way";
  if (kind === "relation_type") return "the same two ideas, joined by a different kind of link";
  return "the structures clash";
}

function shortScore(value) {
  return Number(value).toFixed(2);
}

function placeLabel(location) {
  if (!location) return "Location not shared";
  return `${location.city} · ${location.region}`;
}

function humanRelation(type) {
  return String(type || "").replace(/_/g, " ");
}

// ---- your thought ---------------------------------------------------------

function nodeIndex(context) {
  const byId = new Map();
  for (const node of context?.active_thought?.nodes || []) byId.set(node.id, node);
  return byId;
}

function relationIndex(context) {
  const byId = new Map();
  for (const relation of context?.active_thought?.relations || []) byId.set(relation.id, relation);
  return byId;
}

function relationSentence(relation, nodes) {
  const source = nodes.get(relation.source)?.label || relation.source;
  const target = nodes.get(relation.target)?.label || relation.target;
  return {source, type: relation.type, target};
}

function renderContext(context) {
  const thought = context.active_thought;
  const nodes = thought.nodes;
  const topic = context.presentation?.topic || nodes[0]?.label || "Shared thought";

  setText("thought-id", thought.thought_id);
  const title = document.getElementById("thought-heading");
  title.replaceChildren(document.createTextNode(topic));
  // The fixture thought carries a public caption in `source.text`; a live share
  // carries an empty string there (the raw text is never retained). Nothing is
  // composed on the person's behalf: what is shown is the field, or nothing.
  setText("thought-caption", thought.source?.text || "");

  // On the live product the state line reflects the visitor's real consent
  // state (owned by collab_ui.mjs); the replay narrative must not label a
  // fresh, never-shared guest as "Shared with Resonance".
  if (window.__resonanceWebMCP?.mode !== "live-product") {
    const line = document.getElementById("share-state");
    if (line) {
      line.replaceChildren(el("span", "status-light"), el("span", "", "Shared with Resonance"));
      line.dataset.shared = "true";
    }
  }

  const chain = document.getElementById("dna-chain");
  chain.replaceChildren();
  for (const node of nodes) {
    const row = el("li", "dna-node");
    row.append(el("strong", "", node.label), el("span", "", node.role));
    chain.append(row);
  }

  const byId = nodeIndex(context);
  const relations = document.getElementById("dna-relations");
  relations.replaceChildren();
  for (const relation of thought.relations || []) {
    const sentence = relationSentence(relation, byId);
    const row = el("li", "dna-relation");
    row.append(
      el("span", "", sentence.source),
      el("span", "relation-type", humanRelation(sentence.type)),
      el("span", "", sentence.target),
    );
    relations.append(row);
  }

  const declared = document.getElementById("declared-context");
  declared.replaceChildren();
  const contextValues = [
    ["Field", context.presentation?.domain || "Not shared"],
    ["Where", context.location ? `${context.location.city} · ${context.location.region}` : "Location not shared"],
  ];
  for (const [label, value] of contextValues) {
    const item = el("div");
    item.append(el("dt", "", label), el("dd", "", value));
    declared.append(item);
  }
  setText("request-mode", context.pinned_request.mode);
  setText("request-k", `k=${context.pinned_request.k}`);
}

// ---- matches ------------------------------------------------------------

function firstCorrespondence(match) {
  const correspondence = match.evidence.top_correspondences[0];
  if (!correspondence) return null;
  return correspondence;
}

function strengthWord(structural) {
  const value = clamp01(structural);
  if (value >= 0.85) return "very close";
  if (value >= 0.6) return "close";
  if (value >= 0.35) return "partial";
  return "faint";
}

function renderMatches(payload, primary) {
  const list = document.getElementById("match-list");
  list.replaceChildren();
  primary.forEach((match) => {
    const position = backendPosition(payload, match);
    // A card is a person: the summary is one button that opens their
    // evidence, and below it sits the action that reaches them (rendered by
    // collab_ui.mjs into .match-card__actions). A button inside a button is
    // not valid HTML, which is why the card itself is an article.
    const card = el("article", "match-card");
    card.dataset.sessionId = match.session_id;
    card.dataset.backendScore = String(match.scores.structural);
    card.dataset.backendClassification = match.mode_classification;
    card.dataset.backendPosition = position;
    card.dataset.person = match.person_pseudonym;
    card.dataset.demoPersona = String(match.display.demo_persona === true);
    card.classList.toggle("is-selected", match.session_id === state.selectedSessionId);

    const number = el("span", "match-card__index", position);
    const open = el("button", "match-card__open");
    open.type = "button";
    open.setAttribute("aria-pressed", String(match.session_id === state.selectedSessionId));
    open.setAttribute("aria-label",
      `Why ${match.person_pseudonym} resonates: ${match.display.topic} (returned in position ${position})`);

    const top = el("div", "match-card__top");
    top.append(el("span", "match-card__person", match.person_pseudonym));
    if (match.display.domain) top.append(el("span", "match-card__domain", match.display.domain));
    const topic = el("p", "match-card__topic", match.display.topic);

    const first = firstCorrespondence(match);
    const why = el("p", "match-card__why");
    if (first) {
      why.append(
        el("span", "", first.query_label),
        el("span", "match-card__arrow", " ↔ "),
        el("span", "", first.candidate_label),
      );
    } else {
      why.textContent = "Evidence available";
    }

    // The structural score, as a bar and as the number. The bar is the number
    // drawn, not a judgement about it.
    const strength = el("div", "match-card__strength");
    const bar = el("progress", "strength-bar");
    bar.max = 1;
    bar.value = clamp01(match.scores.structural);
    bar.setAttribute("aria-hidden", "true");
    strength.append(bar,
      el("span", "strength-word", strengthWord(match.scores.structural)),
      el("span", "strength-number", shortScore(match.scores.structural)));

    const meta = el("div", "match-card__meta");
    meta.append(
      el("span", "classification", classificationInWords(match.mode_classification)),
      el("span", "confidence", match.confidence),
      el("span", "location", placeLabel(match.display.location)),
    );
    if (match.evidence.contradiction_count > 0) {
      meta.append(el("span", "contradictions",
        `${match.evidence.contradiction_count} contradiction${match.evidence.contradiction_count === 1 ? "" : "s"}`));
    }
    open.append(top, topic, why, strength, meta);
    // Seeded rows are labelled so a real participant never mistakes them for
    // people who can accept an introduction.
    if (match.display.demo_persona === true) {
      open.append(el("span", "match-card__example", "example from the seeded corpus"));
    }
    card.append(number, open, el("div", "match-card__actions"));
    // The article takes the click so that programmatic `.click()` on the card
    // (deep links, the WebMCP evidence tool) selects it; clicks inside the
    // action row are the collaboration module's and are not selection.
    card.addEventListener("click", (event) => {
      if (event.target.closest(".match-card__actions")) return;
      selectMatch(match.session_id);
    });
    list.append(card);
  });
  setText("shown-count", primary.length === 1 ? "1 person" : `${primary.length} people`);
  setText("response-summary",
          `${payload.matches.length} with the same shape · ${payload.rejected.length} close but not the same`);
  // When something was set aside because its shape is one many unrelated
  // people carry, say so. Watching matches be fewer than the engine found,
  // with nothing to read, is how a person concludes the product is broken.
  setText("shape-note", payload.shape_note || "");
  const empty = document.getElementById("matches-empty");
  if (empty) empty.hidden = primary.length > 0;
}

// ---- evidence -----------------------------------------------------------

const SCORE_FIELDS = [
  "structural", "semantic", "r_direct", "y_systematicity", "coverage_containment",
  "contradiction", "h_sign_conflict",
];

function renderEvidence(match) {
  setText("evidence-kicker", "Why this resonates");
  setText("evidence-heading", `${match.person_pseudonym} · ${match.display.topic}`);
  setText("evidence-subtitle", `${match.display.domain || "field not shared"} · ${placeLabel(match.display.location)}`);
  setText("metric-class", classificationInWords(match.mode_classification));
  setText("metric-structural", formatScore(match.scores.structural));
  setText("metric-confidence", match.confidence);

  const queryNodes = nodeIndex(state.context);
  const mappings = document.getElementById("mapping-list");
  mappings.replaceChildren();
  match.evidence.top_correspondences.forEach((mapping) => {
    const row = el("div", "mapping-row");
    const query = el("div", "mapping-side");
    const role = queryNodes.get(mapping.query_node)?.role;
    query.append(
      el("small", "", role ? role : mapping.query_node),
      el("strong", "", mapping.query_label),
    );
    const candidate = el("div", "mapping-side");
    candidate.append(el("small", "", "theirs"), el("strong", "", mapping.candidate_label));
    row.append(query, el("div", "mapping-arrow", "↔"), candidate);
    mappings.append(row);
  });

  const queryRelations = relationIndex(state.context);
  const relations = document.getElementById("relation-chips");
  relations.replaceChildren();
  match.evidence.preserved_relations.forEach((relation) => {
    const chip = el("span", "relation-chip");
    const known = queryRelations.get(relation.query_relation);
    if (known) {
      // The query side of a preserved relation is resolvable from the visitor's
      // own Thought DNA. The candidate side is only an id: the other person's
      // relations are not in the response, so nothing is invented for them.
      const sentence = relationSentence(known, queryNodes);
      const line = el("span", "relation-chip__query");
      line.append(
        document.createTextNode(`${sentence.source} `),
        el("span", "relation-type", humanRelation(sentence.type)),
        document.createTextNode(` ${sentence.target}`),
      );
      chip.append(line);
    }
    if (!known) {
      // The candidate side is only an id, and the query side did not resolve.
      // An id pair says nothing to the person the panel is for, so say what
      // is actually known instead of printing both.
      chip.append(el("span", "relation-chip__query", "a link both of you keep"));
    }
    relations.append(chip);
  });
  setText(
    "proof-note",
    `${match.evidence.mapped_node_count} nodes correspond · ${match.evidence.preserved_relation_count} relations preserved · ${match.evidence.contradiction_count} contradictions. The engine's evidence, shown unchanged.`,
  );

  const scores = document.getElementById("score-list");
  if (scores) {
    scores.replaceChildren();
    for (const field of SCORE_FIELDS) {
      if (!(field in match.scores)) continue;
      const value = match.scores[field];
      const item = el("div");
      item.append(el("dt", "", field), el("dd", "", typeof value === "number" ? formatScore(value) : String(value)));
      scores.append(item);
    }
  }
}

// ---- map ----------------------------------------------------------------

function mapGeometry() {
  const frame = document.getElementById("map-frame");
  const svg = document.getElementById("resonance-map");
  const narrow = (frame?.clientWidth || 800) < 560;
  const width = narrow ? 560 : 900;
  const height = narrow ? 560 : 620;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  if (frame) frame.dataset.shape = narrow ? "square" : "wide";
  const R = Math.min(width, height) / 2 - (narrow ? 40 : 52);
  return {width, height, cx: width / 2, cy: height / 2, R, narrow};
}

function radialPath(from, to) {
  return `M${from.x.toFixed(1)} ${from.y.toFixed(1)} L${to.x.toFixed(1)} ${to.y.toFixed(1)}`;
}

const SECTOR_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function sectorLetter(index) {
  return SECTOR_LETTERS[index % SECTOR_LETTERS.length] + (index >= SECTOR_LETTERS.length ? String(Math.floor(index / SECTOR_LETTERS.length)) : "");
}

// The sector labels on the map were the slug itself, hyphens and all, broken
// across lines at the hyphens -- so the legend read "retry-storms-after-a-
// partial-outage" and, in a seeded corpus, "unrelated-distractor". A map
// legend is read by whoever is looking at the map.
function wrapSlug(slug, maxChars = 18) {
  const lines = [];
  let current = "";
  for (const part of clusterInWords(slug).split(" ")) {
    const candidate = current ? `${current} ${part}` : part;
    if (current && candidate.length > maxChars) {
      lines.push(current);
      current = part;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function renderRings(geometry, r0, sectorArcs) {
  const rings = document.getElementById("ring-layer");
  rings.replaceChildren();
  const {cx, cy, R, narrow} = geometry;
  const stops = [1, 0.75, 0.5, 0.25, 0];
  for (const structural of stops) {
    const radius = structuralRadius(structural, R, r0);
    rings.append(svgEl("circle", {
      class: `ring${structural === 1 ? " is-inner" : ""}`, cx, cy, r: radius.toFixed(1),
    }));
    const theta = (135 * Math.PI) / 180;
    const label = svgEl("text", {
      class: "ring-label",
      x: (cx + (radius + 3) * Math.cos(theta)).toFixed(1),
      y: (cy + (radius + 3) * Math.sin(theta)).toFixed(1),
      "text-anchor": "end",
    });
    label.textContent = structural.toFixed(2);
    rings.append(label);
  }
  if (sectorArcs.length > 1) {
    for (const arc of sectorArcs) {
      const theta = ((arc.start - SECTOR_GAP_DEG / 2) * Math.PI) / 180;
      rings.append(svgEl("line", {
        class: "sector-line",
        x1: (cx + r0 * 0.5 * Math.cos(theta)).toFixed(1), y1: (cy + r0 * 0.5 * Math.sin(theta)).toFixed(1),
        x2: (cx + (R + 10) * Math.cos(theta)).toFixed(1), y2: (cy + (R + 10) * Math.sin(theta)).toFixed(1),
      }));
    }
  }
  sectorArcs.forEach((arc, index) => {
    const mid = (((arc.start + arc.end) / 2) * Math.PI) / 180;
    const cos = Math.cos(mid);
    const lx = cx + (R + 24) * cos;
    const ly = cy + (R + 24) * Math.sin(mid);
    const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
    const label = svgEl("text", {class: "sector-label", x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": anchor});
    const letter = svgEl("tspan", {class: "sector-letter"});
    letter.textContent = sectorLetter(index);
    label.append(letter);
    if (!narrow) {
      const lines = wrapSlug(arc.cluster);
      lines.forEach((line, lineIndex) => {
        const span = lineIndex === 0 ? svgEl("tspan") : svgEl("tspan", {x: lx.toFixed(1), dy: 13});
        span.textContent = lineIndex === 0 ? ` ${line}` : line;
        label.append(span);
      });
    }
    rings.append(label);
  });
}

function renderSectorKey(sectorArcs) {
  const key = document.getElementById("sector-key");
  if (!key) return;
  key.replaceChildren();
  sectorArcs.forEach((arc, index) => {
    const item = el("li");
    item.append(
      el("span", "sector-key__letter", sectorLetter(index)),
      el("span", "sector-key__name", clusterInWords(arc.cluster)),
      el("span", "sector-key__count", `${arc.count}`),
    );
    key.append(item);
  });
}

function addConnection(layer, from, to, item) {
  const width = item.kind === "primary" ? 1 + 0.4 * Number(item.weight || 0) : 1;
  const classes = ["connection-line"];
  if (item.kind === "other") classes.push("is-other");
  if (item.kind === "rejected") classes.push("is-rejected");
  else if (item.contradiction) classes.push("is-contradiction");
  layer.append(svgEl("path", {
    d: radialPath(from, to),
    class: classes.join(" "),
    "stroke-width": width.toFixed(1),
    "data-session-id": item.sessionId,
  }));
}

function addMarker(layer, item, options) {
  const marker = svgEl("g", {
    class: `marker ${options.kind}${item.contradiction ? " is-contradiction" : ""}`,
    transform: `translate(${item.x.toFixed(1)} ${item.y.toFixed(1)})`,
    "data-session-id": item.sessionId,
    "aria-label": options.ariaLabel,
  });
  if (options.onSelect) {
    marker.setAttribute("role", "button");
    marker.setAttribute("tabindex", "0");
    marker.addEventListener("click", options.onSelect);
    marker.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        options.onSelect();
      }
    });
  }
  if (options.kind === "is-query") {
    // The thought that is out there: a slow breath while it keeps looking.
    marker.append(svgEl("circle", {class: "marker-halo", r: options.radius + 10}));
  }
  if (item.contradiction) marker.append(svgEl("circle", {class: "marker-outline", r: options.radius + 5}));
  marker.append(svgEl("circle", {class: "marker-ring", r: options.radius}));
  if (options.kind === "is-query") marker.append(svgEl("circle", {class: "marker-core", r: 3}));
  if (options.kind === "is-rejected") {
    const s = options.radius * 0.45;
    marker.append(svgEl("path", {class: "marker-cross", d: `M${-s} ${-s}L${s} ${s}M${s} ${-s}L${-s} ${s}`}));
  } else if (options.index) {
    const index = svgEl("text", {class: "marker-index"});
    index.textContent = options.index;
    marker.append(index);
  }
  if (options.label) {
    const angle = item.angle;
    const distance = options.radius + 8;
    const cos = angle === undefined ? 0 : Math.cos(angle);
    const sin = angle === undefined ? -1 : Math.sin(angle);
    const anchor = cos > 0.35 ? "start" : cos < -0.35 ? "end" : "middle";
    const lx = (distance * cos).toFixed(1);
    const ly = (distance * sin + (sin > 0.35 ? 12 : sin < -0.35 ? -4 : 4)).toFixed(1);
    const label = svgEl("text", {class: "marker-label", x: lx, y: ly, "text-anchor": anchor});
    label.textContent = options.label;
    marker.append(label);
    if (options.sublabel) {
      const sublabel = svgEl("text", {class: "marker-sublabel", x: lx, y: (Number(ly) + 13).toFixed(1), "text-anchor": anchor});
      sublabel.textContent = options.sublabel;
      marker.append(sublabel);
    }
  }
  layer.append(marker);
}

function mapItems(payload, primary, others, rejected) {
  const primaryIds = new Set(primary.map((match) => match.session_id));
  const otherIds = new Set(others.map((match) => match.session_id));
  const rejectedIds = new Set(rejected.map((row) => row.session_id));
  const items = [];
  for (const row of [...payload.matches, ...payload.rejected]) {
    let kind = null;
    if (primaryIds.has(row.session_id)) kind = "primary";
    else if (otherIds.has(row.session_id)) kind = "other";
    else if (rejectedIds.has(row.session_id)) kind = "rejected";
    if (!kind) continue;
    if (items.some((item) => item.sessionId === row.session_id)) continue;
    items.push({
      sessionId: row.session_id,
      row,
      kind,
      cluster: row.display?.cluster_id || "",
      structural: row.scores?.structural ?? 0,
      weight: row.evidence?.preserved_relation_count ?? 0,
      contradiction: (row.evidence?.contradiction_count ?? 0) > 0,
      position: backendPosition(payload, row),
    });
  }
  return items;
}

function renderMap(context, payload, primary, others, rejected) {
  const connections = document.getElementById("connection-layer");
  const markers = document.getElementById("marker-layer");
  connections.replaceChildren();
  markers.replaceChildren();

  const geometry = mapGeometry();
  const items = mapItems(payload, primary, others, rejected);
  const {placed, sectorArcs, r0} = layoutMap(items, geometry);
  renderRings(geometry, r0, sectorArcs);
  renderSectorKey(sectorArcs);

  const centre = {x: geometry.cx, y: geometry.cy};
  const topic = context?.presentation?.topic || context?.active_thought?.nodes?.[0]?.label || "Your thought";
  addMarker(markers, {...centre, sessionId: "active-thought", contradiction: false}, {
    kind: "is-query",
    ariaLabel: `Your thought: ${topic}`,
    label: placed.length ? "Your thought" : "Your thought, out here",
    radius: 11,
  });

  for (const item of placed) addConnection(connections, centre, item, item);

  let unlocatedPrimary = null;
  for (const item of placed) {
    const row = item.row;
    if (item.kind === "primary") {
      if (!row.display.location) unlocatedPrimary ||= row;
      addMarker(markers, item, {
        kind: "is-primary",
        ariaLabel: `${row.person_pseudonym}, structural ${formatScore(row.scores.structural)}, returned in position ${item.position}`,
        label: row.person_pseudonym,
        sublabel: `${classificationInWords(row.mode_classification)} · ${formatScore(row.scores.structural)}`,
        index: item.position,
        radius: 12,
        onSelect: () => selectMatch(row.session_id),
      });
    } else if (item.kind === "other") {
      addMarker(markers, item, {
        kind: "is-other",
        ariaLabel: `Other returned match ${item.position}: ${row.person_pseudonym}, structural ${formatScore(row.scores.structural)}`,
        label: row.person_pseudonym,
        sublabel: `${classificationInWords(row.mode_classification)} · ${formatScore(row.scores.structural)}`,
        index: item.position,
        radius: 9,
        onSelect: () => openDrawerAt(row.session_id),
      });
    } else {
      addMarker(markers, item, {
        kind: "is-rejected",
        ariaLabel: `Refused ${item.position}: ${row.person_pseudonym}, ${rejectionInWords(row.hard_rejection)}`,
        label: row.person_pseudonym,
        sublabel: rejectionInWords(row.hard_rejection),
        radius: 8,
        onSelect: () => openDrawerAt(row.session_id),
      });
    }
  }

  const frame = document.getElementById("map-frame");
  if (frame) frame.dataset.empty = String(placed.length === 0);
  const unlocated = document.getElementById("unlocated-anchor");
  unlocated.hidden = !unlocatedPrimary;
  if (unlocatedPrimary) setText("unlocated-name", unlocatedPrimary.person_pseudonym);
  document.getElementById("map-status").classList.remove("is-loading");
}

function renderContradictions(rejected) {
  const card = document.getElementById("contradiction-card");
  card.hidden = rejected.length === 0;
  if (!rejected.length) return;
  const first = rejected[0];
  setText("contradiction-topic", first.display.topic);
  setText("contradiction-person", first.person_pseudonym);
  setText("contradiction-reason",
          `${rejectionInWords(first.hard_rejection)}, so this is not called a resonance`);
  setText("rejected-count", rejected.length === 1
    ? "1 near miss like this"
    : `${rejected.length} near misses like this`);
}

function drawerRow(payload, row, rejected = false) {
  const item = el("div", "drawer-row");
  item.dataset.sessionId = row.session_id;
  item.append(el("span", "drawer-row__order", backendPosition(payload, row)));
  const copy = el("div");
  copy.append(el("strong", "", `${row.person_pseudonym} · ${row.display.topic}`));
  copy.append(el("span", "",
    `${classificationInWords(row.mode_classification)} · ${row.confidence} confidence · ${placeLabel(row.display.location)}`));
  item.append(copy, el("span", "row-figure",
    rejected ? rejectionInWords(row.hard_rejection) : formatScore(row.scores.structural)));
  return item;
}

function renderDrawer(payload, others, rejected) {
  setText("secondary-count", String(others.length + rejected.length));
  const trigger = document.getElementById("secondary-trigger");
  trigger.disabled = others.length + rejected.length === 0;
  trigger.hidden = trigger.disabled;

  const matches = document.getElementById("drawer-matches");
  const rejectedList = document.getElementById("drawer-rejected");
  matches.replaceChildren();
  rejectedList.replaceChildren();
  others.forEach((match) => matches.append(drawerRow(payload, match)));
  rejected.forEach((match) => rejectedList.append(drawerRow(payload, match, true)));
}

function updateSelection() {
  document.querySelectorAll("[data-session-id]").forEach((node) => {
    const selected = node.dataset.sessionId === state.selectedSessionId;
    if (node.classList.contains("match-card") || node.classList.contains("marker") || node.classList.contains("connection-line")) {
      node.classList.toggle("is-selected", selected);
    }
    if (node.classList.contains("match-card")) {
      node.querySelector(".match-card__open")?.setAttribute("aria-pressed", String(selected));
    }
  });
}

// Somebody else on the page — an alert about a person who arrived after the
// share — wants a session shown. It is a primary card, a row in the other
// results, or not in the current answer at all; say which.
function focusSession(sessionId) {
  if (!sessionId || !state.payload) { showToast("Not in the current result"); return; }
  if (state.primary.some((match) => match.session_id === sessionId)) {
    selectMatch(sessionId);
    document.querySelector(`.match-card[data-session-id="${CSS.escape(sessionId)}"]`)
      ?.scrollIntoView({block: "center"});
    return;
  }
  if (document.querySelector(`.drawer-row[data-session-id="${CSS.escape(sessionId)}"]`)) {
    openDrawerAt(sessionId);
    return;
  }
  showToast("Not in the current result — it may rank below the returned list");
}

function selectMatch(sessionId) {
  const match = state.primary.find((candidate) => candidate.session_id === sessionId);
  if (!match) return;
  state.selectedSessionId = sessionId;
  updateSelection();
  renderEvidence(match);
}

function openDrawerAt(sessionId) {
  setDrawer(true);
  document.querySelectorAll(".drawer-row").forEach((row) => {
    row.classList.toggle("is-highlighted", row.dataset.sessionId === sessionId);
  });
  document.querySelector(`.drawer-row[data-session-id="${CSS.escape(sessionId)}"]`)
    ?.scrollIntoView({block: "center"});
}

// Everything below is owned by a rendered discovery result. Whenever a result
// stops being on screen, ALL of it has to go, so no evidence for a result that
// was never returned survives next to a new message.
function clearResults() {
  state.payload = null;
  state.primary = [];
  state.selectedSessionId = null;

  document.getElementById("match-list")?.replaceChildren();
  setText("shown-count", "");
  const empty = document.getElementById("matches-empty");
  if (empty) empty.hidden = true;

  setText("evidence-kicker", "Why this resonates");
  setText("evidence-heading", "Select a person");
  setText("evidence-subtitle", "");
  setText("metric-class", "—");
  setText("metric-structural", "—");
  setText("metric-confidence", "—");
  document.getElementById("mapping-list")?.replaceChildren();
  document.getElementById("relation-chips")?.replaceChildren();
  document.getElementById("score-list")?.replaceChildren();
  setText("proof-note", "");

  document.getElementById("ring-layer")?.replaceChildren();
  document.getElementById("sector-key")?.replaceChildren();
  document.getElementById("connection-layer")?.replaceChildren();
  document.getElementById("marker-layer")?.replaceChildren();
  const unlocated = document.getElementById("unlocated-anchor");
  if (unlocated) unlocated.hidden = true;
  document.getElementById("map-status")?.classList.remove("is-loading");

  const card = document.getElementById("contradiction-card");
  if (card) card.hidden = true;

  setText("secondary-count", "0");
  const trigger = document.getElementById("secondary-trigger");
  if (trigger) { trigger.disabled = true; trigger.hidden = true; }
  document.getElementById("drawer-matches")?.replaceChildren();
  document.getElementById("drawer-rejected")?.replaceChildren();
}

// A discovery that returns candidates but none that clear the resonance bar,
// or none at all, is the usual first answer and not a failure. The thought is
// out there; the map shows it there, alone for now.
function renderEmpty(payload) {
  clearResults();
  state.payload = payload;
  const rejected = visibleRejected(payload);
  const others = visibleOtherMatches(payload, []);
  renderContradictions(rejected);
  renderDrawer(payload, others, rejected);
  renderMap(state.context, payload, [], others, rejected);
  const empty = document.getElementById("matches-empty");
  if (empty) {
    empty.hidden = false;
    // The engine can return rows it will not call a resonance — a close
    // skeleton with no concept evidence behind it, say. They are real
    // people and they are on the map and in the roster; say so rather than
    // letting "nobody" sit next to a marker.
    let more = empty.querySelector(".waiting-more");
    if (!more) { more = el("p", "waiting-copy waiting-more"); empty.append(more); }
    const returned = others.length;
    more.textContent = returned
      ? `${returned === 1 ? "One thought" : `${returned} thoughts`} came back with a similar skeleton, which the engine will not call a resonance on structure alone. ${returned === 1 ? "It is" : "They are"} on the map and below, and open to an introduction all the same.`
      : "";
    more.hidden = !returned;
  }
  setText("response-summary", `${payload.matches.length} returned · 0 resonances · ${payload.rejected.length} refused`);
  setText("map-status-text", others.length
    ? `${others.length} returned, none the engine calls a resonance · still looking`
    : "Nobody yet · still looking");
  setText("source-note", "Your shared thought, live. Nobody has cleared the bar yet; it keeps looking.");
  setShellState("empty");
}

function renderDiscovery(payload) {
  const primary = selectPrimaryMatches(payload);
  if (!primary.length) {
    renderEmpty(payload);
    return;
  }
  state.payload = payload;
  state.primary = primary;
  state.selectedSessionId = primary[0].session_id;
  const others = visibleOtherMatches(payload, primary);
  const rejected = visibleRejected(payload);

  renderMatches(payload, primary);
  renderMap(state.context, payload, primary, others, rejected);
  renderContradictions(rejected);
  renderDrawer(payload, others, rejected);
  renderEvidence(primary[0]);
  updateSelection();
  const extra = others.length + rejected.length;
  setText("map-status-text",
    `${primary.length} ${primary.length === 1 ? "person" : "people"} with the same shape` +
    (extra ? ` · ${extra} more returned` : ""));
  setText("source-note", "Your shared thought, live: these are people who have shared one too.");
  setShellState("ready");
}

function setLoading(loading) {
  document.getElementById("map-status").classList.toggle("is-loading", loading);
  if (loading) setText("map-status-text", "Looking…");
}

// The visitor's own panel, emptied. `clearResults()` owns the discovery
// surfaces; this owns the "Your thought" panel.
function clearActiveThought() {
  state.context = null;
  setText("thought-id", "—");
  const title = document.getElementById("thought-heading");
  title.replaceChildren(document.createTextNode("Share one thought"));
  setText("thought-caption",
    "In your own words: what causes what, what prevents what. You will see exactly what would become visible before it does.");
  document.getElementById("dna-chain")?.replaceChildren();
  document.getElementById("dna-relations")?.replaceChildren();
  document.getElementById("declared-context")?.replaceChildren();
  setText("request-mode", CANONICAL_MODE);
  setText("request-k", `k=${CANONICAL_K}`);
}

// A visitor who has shared nothing is the product's normal starting state, not
// an error and not a reason to show invented people. It gets its own state.
function renderUnshared() {
  clearResults();
  clearActiveThought();
  setText("response-summary", "Nothing shared · nothing searched");
  setText("map-status-text", "Nothing shared yet");
  setText("source-note", "Nothing of yours is discoverable, so nothing was searched for.");
  setShellState("unshared");
  setLoading(false);
}

function showError(error) {
  setShellState("error");
  clearResults();
  setText("response-summary", "—");
  setText("map-status-text", "Could not read the result");
  setText("source-note", "Nothing is shown, because nothing could be read.");
  document.dispatchEvent(new CustomEvent("resonance:notice",
    {detail: {message: `Discovery could not be read: ${error.message}`}}));
  setLoading(false);
}

async function loadResults() {
  setLoading(true);
  try {
    const [response, contextResponse] = await Promise.all([
      fetch("/api/discover", {cache: "no-store"}),
      fetch("/api/context", {cache: "no-store"}),
    ]);
    const payload = await response.json();
    // 409 share_required: nothing of theirs is discoverable. 401: the cookie
    // names a session this server no longer knows (it restarted, or the
    // session was revoked) — which, to a reader, is the same fact.
    if ((response.status === 409 && payload?.error === SHARE_REQUIRED) || response.status === 401) {
      renderUnshared();
      return;
    }
    if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    assertAcceptedDiscovery(payload);
    if (contextResponse.ok) {
      const context = await contextResponse.json();
      assertAcceptedContext(context);
      state.context = context;
      renderContext(context);
    }
    renderDiscovery(payload);
    setLoading(false);
  } catch (error) {
    showError(error);
  }
}

function setDrawer(open) {
  const drawer = document.getElementById("secondary-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  drawer.classList.toggle("is-open", open);
  drawer.setAttribute("aria-hidden", String(!open));
  drawer.inert = !open;
  backdrop.hidden = !open;
  document.getElementById("secondary-trigger").setAttribute("aria-expanded", String(open));
  if (open) document.getElementById("drawer-close").focus();
  else document.querySelectorAll(".drawer-row.is-highlighted").forEach((row) => row.classList.remove("is-highlighted"));
}

function showToast(message) {
  document.dispatchEvent(new CustomEvent("resonance:toast", {detail: {message}}));
}

// ---- connect a chat -----------------------------------------------------
//
// The instructions are static markup; the runtime supplies the origin (the
// page is reachable on more than one host, and the address must be the one
// you actually opened), the copy button, the client picker, and the truth
// about THIS browser's WebMCP surface.

function wireConnect() {
  const origin = window.location.origin;
  const mcpUrl = `${origin}/mcp`;
  const urlNode = document.getElementById("mcp-url");
  if (urlNode) urlNode.textContent = mcpUrl;
  for (const node of document.querySelectorAll(".onboarding-inline-code")) {
    node.textContent = node.textContent.replace(/https:\/\/[a-z0-9.-]+\/mcp/gi, mcpUrl);
  }

  const copy = document.getElementById("copy-mcp-url");
  copy?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(mcpUrl);
      showToast("Address copied");
    } catch {
      showToast(mcpUrl);
    }
  });

  // One client at a time: a tab list, arrow keys included.
  const tabs = [...document.querySelectorAll("#client-tabs [role=tab]")];
  const select = (tab, focus = false) => {
    for (const other of tabs) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      other.tabIndex = selected ? 0 : -1;
      const panel = document.getElementById(other.getAttribute("aria-controls"));
      if (panel) panel.hidden = !selected;
    }
    if (focus) tab.focus();
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (event.key === "Home") { event.preventDefault(); select(tabs[0], true); return; }
      if (event.key === "End") { event.preventDefault(); select(tabs[tabs.length - 1], true); return; }
      if (!delta) return;
      event.preventDefault();
      select(tabs[(index + delta + tabs.length) % tabs.length], true);
    });
  });

  // Say what is true of THIS browser — but say it about the browser, not about
  // the product. Resonance speaks both transports either way.
  const webmcp = document.getElementById("onboarding-webmcp-copy");
  if (webmcp) {
    webmcp.textContent = (document.modelContext || navigator.modelContext)
      ? "Resonance also speaks WebMCP, and this browser has it: the tools on this "
        + "page are registered through document.modelContext right now, with no "
        + "connector at all."
      : "Resonance also speaks WebMCP, but this browser does not expose "
        + "document.modelContext, so there is nothing for it to register here. "
        + "Chrome 152 exposes it when started with --enable-features=WebMCP. The "
        + "connectors above need no such thing and reach the same product.";
  }
}

// Re-read the live view when what is discoverable changes.
//
// This must cost ZERO extra requests: discovery is rate-limited, and a read
// per write is enough to push a busy sequence over the limit. The modules
// that write already hold the state and announce it on `resonance:consent`;
// this only listens, and only re-reads when the announcement differs from
// the last one.
//
// "Differs" used to mean the yes/no of sharing flipped. With two thoughts
// shared, withdrawing one flips nothing -- and the page kept drawing the
// withdrawn thought under "What others can see", telling a person they were
// still sharing the thing they had just taken back. So an announcement that
// says WHICH thoughts are discoverable (collab_ui.mjs sends the list) is
// compared as a set -- membership, not order: this module orders nothing --
// and one that only says whether anything is (webmcp_live.mjs) is compared
// as before, because that is all it knows. The identifiers are compared and
// never shown.
export function consentWatcher(reread) {
  let last = null;
  const sameSet = (a, b) => a.size === b.size && [...a].every((id) => b.has(id));
  return (detail) => {
    const shared = detail?.shared === true;
    const which = Array.isArray(detail?.discoverable)
      ? new Set(detail.discoverable.map(String)) : null;
    if (last === null) {
      last = {shared, which};
      return;
    }
    const changed = which !== null && last.which !== null
      ? !sameSet(which, last.which)
      : shared !== last.shared;
    last = {shared, which: which ?? last.which};
    if (changed) reread();
  };
}
const onConsentState = consentWatcher(() => { loadResults(); });

let resizeTimer;
function onResize() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (!state.payload) return;
    const shell = document.getElementById("app-shell").dataset.state;
    if (shell !== "ready" && shell !== "empty") return;
    const primary = state.primary;
    renderMap(state.context, state.payload, primary,
      visibleOtherMatches(state.payload, primary), visibleRejected(state.payload));
    updateSelection();
  }, 120);
}

async function boot() {
  try {
    const contextResponse = await fetch("/api/context", {cache: "no-store"});
    // A first-time visitor has no context of their own: /api/context answers
    // 409 share_required rather than handing back somebody else's thought.
    const context = await contextResponse.json().catch(() => null);
    const unshared = (contextResponse.status === 409 && context?.error === SHARE_REQUIRED)
      || contextResponse.status === 401;
    if (!unshared) {
      if (!contextResponse.ok) throw new Error("Presentation context is unavailable");
      assertAcceptedContext(context);
      state.context = context;
      renderContext(context);
    }

    wireConnect();
    document.addEventListener("resonance:consent", (event) => {
      onConsentState(event.detail);
    });
    // An agent can run a discovery through the WebMCP tools without touching
    // this page; the transport says when it has, and the page re-reads.
    document.addEventListener("resonance:discovered", () => { loadResults(); });
    // An alert about a person who arrived after the share asks for them to be
    // shown on the map and in the evidence.
    document.addEventListener("resonance:focus-session", (event) => {
      focusSession(event.detail?.sessionId);
      document.getElementById("people")?.scrollIntoView({block: "start"});
    });
    document.getElementById("secondary-trigger").addEventListener("click", () => setDrawer(true));
    document.getElementById("drawer-close").addEventListener("click", () => setDrawer(false));
    document.getElementById("drawer-backdrop").addEventListener("click", () => setDrawer(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setDrawer(false);
    });
    window.addEventListener("resize", onResize);

    await loadResults();
  } catch (error) {
    showError(error);
  }
}

if (typeof document !== "undefined") boot();
