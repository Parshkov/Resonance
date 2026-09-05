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
// renumbers, so the order is recoverable from any surface (card, marker,
// drawer row) without trusting the layout.
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
// Nothing here ranks, scores or moves a row ahead of another.
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
  // items: [{sessionId, cluster, structural, ...}] already in backend order.
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

function formatScore(value) {
  return Number(value).toFixed(4);
}

function placeLabel(location) {
  if (!location) return "Location not shared";
  return `${location.city} · ${location.region}`;
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
  const mechanism = nodes.find((node) => node.role === "mechanism")?.label || nodes[1]?.label;

  setText("thought-id", thought.thought_id);
  const title = document.getElementById("thought-heading");
  title.replaceChildren();
  title.append(document.createTextNode(topic));
  if (mechanism) {
    title.append(el("span", "chain-arrow", " → "));
    title.append(document.createTextNode(mechanism));
  }
  // The fixture thought carries a public caption in `source.text`; a live share
  // carries an empty string there (the raw text is never retained). Nothing is
  // composed on the person's behalf: what is shown is the field, or nothing.
  setText("thought-caption", thought.source?.text || "");

  // On the live product the header pill reflects the visitor's real consent
  // state (owned by webmcp_live.mjs); the replay narrative must not label a
  // fresh, never-shared guest as "Shared with Resonance".
  if (window.__resonanceWebMCP?.mode !== "live-product") {
    const consent = document.getElementById("header-consent");
    consent.replaceChildren(el("span", "status-light"), el("span", "", "Shared with Resonance"));
  }

  const chain = document.getElementById("dna-chain");
  chain.replaceChildren();
  for (const node of nodes) {
    const row = el("li", "dna-node");
    row.append(el("code", "", node.id), el("strong", "", node.label), el("span", "", node.role));
    chain.append(row);
  }

  const byId = nodeIndex(context);
  const relations = document.getElementById("dna-relations");
  relations.replaceChildren();
  for (const relation of thought.relations || []) {
    const sentence = relationSentence(relation, byId);
    const row = el("li", "dna-relation");
    row.append(
      el("code", "", relation.id),
      el("span", "", sentence.source),
      el("span", "relation-type", sentence.type),
      el("span", "", sentence.target),
    );
    relations.append(row);
  }

  const declared = document.getElementById("declared-context");
  declared.replaceChildren();
  const contextValues = [
    ["Domain", context.presentation?.domain || "Not shared"],
    ["Coarse location", context.location ? `${context.location.city} · ${context.location.region}` : "Not shared"],
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
  if (!correspondence) return "Evidence mapping available";
  return `${correspondence.query_label} ↔ ${correspondence.candidate_label}`;
}

function renderMatches(payload, primary) {
  const list = document.getElementById("match-list");
  list.replaceChildren();
  primary.forEach((match) => {
    const position = backendPosition(payload, match);
    const button = el("button", "match-card");
    button.type = "button";
    button.dataset.sessionId = match.session_id;
    button.dataset.backendScore = String(match.scores.structural);
    button.dataset.backendClassification = match.mode_classification;
    button.dataset.backendPosition = position;
    button.setAttribute("aria-pressed", String(match.session_id === state.selectedSessionId));
    button.setAttribute("aria-label",
      `Open evidence for ${match.person_pseudonym}: ${match.display.topic} (returned in position ${position})`);

    const number = el("span", "match-card__index", position);
    const top = el("div", "match-card__top");
    top.append(
      el("span", "match-card__person", match.person_pseudonym),
      el("span", "match-card__score", `structural ${formatScore(match.scores.structural)}`),
    );
    const topic = el("p", "match-card__topic", match.display.topic);
    const why = el("p", "match-card__why", firstCorrespondence(match));
    const meta = el("div", "match-card__meta");
    meta.append(
      el("span", "classification", match.mode_classification),
      el("span", "confidence", `confidence ${match.confidence}`),
      el("span", "location", placeLabel(match.display.location)),
    );
    if (match.evidence.contradiction_count > 0) {
      meta.append(el("span", "contradictions",
        `${match.evidence.contradiction_count} contradiction${match.evidence.contradiction_count === 1 ? "" : "s"}`));
    }
    button.append(number, top, topic, why, meta);
    button.addEventListener("click", () => selectMatch(match.session_id));
    list.append(button);
  });
  setText("shown-count", `${String(primary.length).padStart(2, "0")} shown`);
  setText("response-summary", `${payload.matches.length} matches · ${payload.rejected.length} rejected`);
  const empty = document.getElementById("matches-empty");
  if (empty) empty.hidden = primary.length > 0;
}

// ---- evidence -----------------------------------------------------------

const SCORE_FIELDS = [
  "structural", "semantic", "r_direct", "y_systematicity", "coverage_containment",
  "contradiction", "h_sign_conflict",
];

function renderEvidence(match) {
  setText("evidence-kicker", `Why ${match.person_pseudonym} resonates`);
  setText("evidence-heading", match.display.topic);
  setText("evidence-subtitle", `${match.display.domain} · ${placeLabel(match.display.location)}`);
  setText("metric-class", match.mode_classification);
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
      el("small", "", role ? `${mapping.query_node} · ${role}` : mapping.query_node),
      el("strong", "", mapping.query_label),
    );
    const candidate = el("div", "mapping-side");
    candidate.append(el("small", "", mapping.candidate_node), el("strong", "", mapping.candidate_label));
    row.append(query, el("div", "mapping-arrow", "↔"), candidate);
    mappings.append(row);
  });

  const queryRelations = relationIndex(state.context);
  const relations = document.getElementById("relation-chips");
  relations.replaceChildren();
  match.evidence.preserved_relations.forEach((relation) => {
    const chip = el("span", "relation-chip");
    chip.append(el("span", "relation-chip__pair", `${relation.query_relation} ↔ ${relation.candidate_relation}`));
    const known = queryRelations.get(relation.query_relation);
    if (known) {
      // The query side of a preserved relation is resolvable from the visitor's
      // own Thought DNA. The candidate side is only an id: the other person's
      // relations are not in the response, so nothing is invented for them.
      const sentence = relationSentence(known, queryNodes);
      const line = el("span", "relation-chip__query");
      line.append(
        document.createTextNode(`${sentence.source} `),
        el("span", "relation-type", sentence.type),
        document.createTextNode(` ${sentence.target}`),
      );
      chip.append(line);
    }
    relations.append(chip);
  });
  setText(
    "proof-note",
    `${match.evidence.mapped_node_count} mapped nodes · ${match.evidence.preserved_relation_count} preserved · ${match.evidence.contradiction_count} contradictions. Backend evidence, presented unchanged.`,
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
  const narrow = (frame?.clientWidth || 800) < 600;
  const width = narrow ? 560 : 900;
  const height = narrow ? 560 : 620;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  if (frame) frame.dataset.shape = narrow ? "square" : "wide";
  // Room outside the rim for the sector letters and, in the wide layout, the
  // cluster names beside them.
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

// Cluster ids are hyphenated slugs; break them at hyphens into short lines so
// a name fits beside the rim instead of running off the drawing.
function wrapSlug(slug, maxChars = 18) {
  const lines = [];
  let current = "";
  for (const part of String(slug).split("-")) {
    const candidate = current ? `${current}-${part}` : part;
    if (current && candidate.length > maxChars) {
      lines.push(`${current}-`);
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
    // Ring values sit along the lower-left diagonal, away from the sector
    // names, which live outside the rim.
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
      el("code", "", arc.cluster),
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
    // Labels sit on the far side of the marker from the centre, so neighbours
    // on the same ring do not stack on top of each other. The centre marker
    // has no angle: its label goes above.
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
  // Backend order across the whole response: matches[] then rejected[].
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
    label: "Your thought",
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
        sublabel: `${row.mode_classification} · ${formatScore(row.scores.structural)}`,
        index: item.position,
        radius: 12,
        onSelect: () => selectMatch(row.session_id),
      });
    } else if (item.kind === "other") {
      addMarker(markers, item, {
        kind: "is-other",
        ariaLabel: `Other returned match ${item.position}: ${row.person_pseudonym}, structural ${formatScore(row.scores.structural)}`,
        label: row.person_pseudonym,
        sublabel: `${row.mode_classification} · ${formatScore(row.scores.structural)}`,
        index: item.position,
        radius: 9,
        onSelect: () => openDrawerAt(row.session_id),
      });
    } else {
      addMarker(markers, item, {
        kind: "is-rejected",
        ariaLabel: `Hard-rejected ${item.position}: ${row.person_pseudonym}, ${row.hard_rejection}`,
        label: row.person_pseudonym,
        sublabel: row.hard_rejection,
        radius: 8,
        onSelect: () => openDrawerAt(row.session_id),
      });
    }
  }

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
  setText("contradiction-reason", first.hard_rejection);
  setText("rejected-count", `${rejected.length} rejected`);
}

function drawerRow(payload, row, rejected = false) {
  const item = el("div", "drawer-row");
  item.dataset.sessionId = row.session_id;
  item.append(el("span", "drawer-row__order", backendPosition(payload, row)));
  const copy = el("div");
  copy.append(el("strong", "", `${row.person_pseudonym} · ${row.display.topic}`));
  copy.append(el("span", "", `${row.mode_classification} · ${row.confidence} · ${placeLabel(row.display.location)}`));
  item.append(copy, el("code", "", rejected ? row.hard_rejection : formatScore(row.scores.structural)));
  return item;
}

function renderDrawer(payload, others, rejected) {
  setText("secondary-count", String(others.length + rejected.length));
  const trigger = document.getElementById("secondary-trigger");
  trigger.disabled = others.length + rejected.length === 0;

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
    if (node.classList.contains("match-card")) node.setAttribute("aria-pressed", String(selected));
  });
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
// stops being on screen — a failure, or a successful discovery in which nothing
// cleared the resonance bar — ALL of it has to go. Clearing only the match list
// used to leave the previous source's evidence, mapping rows, drawer contents,
// contradiction card and response counts on screen next to the new source's
// message, which reads as evidence for a result that was never returned.
function clearResults() {
  state.payload = null;
  state.primary = [];
  state.selectedSessionId = null;

  document.getElementById("match-list")?.replaceChildren();
  setText("shown-count", "00 shown");
  const empty = document.getElementById("matches-empty");
  if (empty) empty.hidden = true;

  setText("evidence-kicker", "Evidence");
  setText("metric-class", "—");
  setText("metric-structural", "—");
  setText("metric-confidence", "—");
  document.getElementById("mapping-list")?.replaceChildren();
  document.getElementById("relation-chips")?.replaceChildren();
  document.getElementById("score-list")?.replaceChildren();
  setText("proof-note", "No frontend matching or score calculation.");

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
  if (trigger) trigger.disabled = true;
  document.getElementById("drawer-matches")?.replaceChildren();
  document.getElementById("drawer-rejected")?.replaceChildren();

}

// A discovery that returns candidates but none that clear the resonance bar is
// a real, correct answer — the backend refusing to advertise a false analogy —
// not a failure. It gets its own state and its own honest counts instead of
// being reported through the error path.
function renderEmpty(payload) {
  clearResults();
  state.payload = payload;
  const rejected = visibleRejected(payload);
  const others = visibleOtherMatches(payload, []);
  renderContradictions(rejected);
  renderDrawer(payload, others, rejected);
  renderMap(state.context, payload, [], others, rejected);
  const empty = document.getElementById("matches-empty");
  if (empty) empty.hidden = false;
  setText("response-summary", `${payload.matches.length} returned · 0 resonances · ${payload.rejected.length} rejected`);
  setText("evidence-kicker", "No resonance yet");
  setText("evidence-heading", "Nothing cleared the resonance bar");
  setText("evidence-subtitle",
    `${payload.matches.length} candidate${payload.matches.length === 1 ? "" : "s"} came back and every one was refused as a resonance. `
    + "Open “Other returned results” to inspect them.");
  setText("map-status-text", "0 resonances · every returned candidate was refused");
  setText("source-note",
    "Live result for your shared thought · nobody cleared the resonance bar this time.");
  document.getElementById("app-shell").dataset.state = "empty";
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
  setText("map-status-text",
    `${primary.length} resonance${primary.length === 1 ? "" : "s"} · ${others.length} other returned · ${rejected.length} rejected · engine order kept`);

  setText("source-note",
    "Live result for your shared thought · these are people who have shared one too.");
  document.getElementById("app-shell").dataset.state = "ready";
}

function setLoading(loading) {
  document.getElementById("map-status").classList.toggle("is-loading", loading);
  if (loading) setText("map-status-text", "Finding people who resonate…");
}

// The visitor's own panel, emptied. `clearResults()` owns the discovery
// surfaces; this owns the "Your thought" panel, which is the surface that
// used to show the fixture thought to somebody who had shared nothing.
function clearActiveThought() {
  state.context = null;
  setText("thought-id", "No thought shared yet");
  const title = document.getElementById("thought-heading");
  title.replaceChildren(document.createTextNode("Nothing shared with Resonance"));
  setText("thought-caption", "Resonance holds no thought for this visitor.");
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
  setText("response-summary", "Nothing shared · nothing discovered");
  setText("map-status-text", "Nothing shared yet · no discovery was run");
  setText("evidence-kicker", "Nothing shared yet");
  setText("evidence-heading", "Share a thought to see who resonates");
  setText("evidence-subtitle",
    "Resonance compares the causal structure of a thought you have explicitly "
    + "shared. Until you share one there is nothing to compare, so nothing is "
    + "shown. Connect an agent to this page or to the Resonance MCP connector, "
    + "prepare a thought, read the preview, and confirm the share.");
  setText("source-note", "You have shared nothing, so nothing was searched for.");
  document.getElementById("app-shell").dataset.state = "unshared";
  setLoading(false);
}

function showError(error) {
  document.getElementById("app-shell").dataset.state = "error";
  // Never leave the previous source's cards, evidence, drawer, counts or map on
  // screen next to an error for the current one.
  clearResults();
  setText("response-summary", "—");
  setText("evidence-kicker", "Discovery unavailable");
  setText("evidence-heading", "No resonance to show");
  setText("evidence-subtitle", error.message);
  setText("map-status-text", `Discovery unavailable: ${error.message}`);
  setText("source-note", "Nothing is shown, because nothing could be read.");
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
    if (response.status === 409 && payload?.error === SHARE_REQUIRED) {
      renderUnshared();
      return;
    }
    if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    assertAcceptedDiscovery(payload);
    // The thought panel shows the visitor's own shared thought, which is the
    // only thought this page ever displays.
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

let toastTimer;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 1800);
}

// The onboarding panel is static markup; only three things about it depend on
// the runtime: which origin is serving (the page is reachable on more than one
// host, and the connector URL must be the one you actually opened), whether
// this browser has an agent surface, and the connect button.
function wireOnboarding() {
  const origin = window.location.origin;
  const mcpUrl = `${origin}/mcp`;
  const urlNode = document.getElementById("mcp-url");
  if (urlNode) urlNode.textContent = mcpUrl;
  for (const node of document.querySelectorAll(".onboarding-inline-code")) {
    // Keep the copy-pasteable snippets honest about the host in the address bar.
    node.textContent = node.textContent.replace(
      /https:\/\/[a-z0-9.-]+\/mcp/gi, mcpUrl);
  }

  const copy = document.getElementById("copy-mcp-url");
  copy?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(mcpUrl);
      showToast("Connector URL copied");
    } catch {
      showToast(mcpUrl);
    }
  });

  document.getElementById("onboarding-connect")?.addEventListener("click", () => {
    document.getElementById("onboarding-connect-panel")?.scrollIntoView({block: "start"});
  });

  // Say what is true of THIS browser — but say it about the browser, not about
  // the product. The earlier wording ("there is nothing to register here")
  // read as though Resonance had no WebMCP support, when what is missing is the
  // browser's agent surface. The service speaks both transports either way.
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

// Leave (or return to) the onboarding state when consent actually changes.
//
// This must cost ZERO extra requests. Two earlier versions did not, and both
// broke Card A's revoke step with "rate limit exceeded": re-running discovery
// on every write drains a rate-limited action outright, and even a cheap
// consent read on every write is enough to push an already busy sequence over
// the limit (30 tokens, refill 1/s). Verified against pristine `main` on the
// same machine, where the same step passes.
//
// The state is already in hand: `webmcp_live.mjs` reads it after every tool
// write and the collaboration panel reads it after every panel write. They
// announce it on `resonance:consent`; this only listens, and only re-reads the
// live view when the answer flipped.
let lastShared = null;
function onConsentState(shared) {
  if (lastShared === null) {                 // first read: boot's loadResults already ran
    lastShared = shared;
    return;
  }
  if (shared === lastShared) return;
  lastShared = shared;
  loadResults();
}

// The map is re-laid out from the state already in hand when the frame
// changes width (the viewBox switches between wide and square). No request.
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
    // That is a state to render, not a boot failure — loadResults renders it
    // below.
    const context = await contextResponse.json().catch(() => null);
    const unshared = contextResponse.status === 409 && context?.error === SHARE_REQUIRED;
    if (!unshared) {
      if (!contextResponse.ok) throw new Error("Presentation context is unavailable");
      assertAcceptedContext(context);
      state.context = context;
      renderContext(context);
    }

    wireOnboarding();
    // The onboarding state is "this visitor has shared nothing", and that can
    // stop being true without a reload: an agent shares through the WebMCP
    // tools, or the visitor shares from the Collaboration panel. Both go
    // through session.mjs, which announces every successful write.
    //
    // Both surfaces already hold the authoritative consent state after a write
    // and announce it here, so this costs no additional request. See
    // `onConsentState` for why that matters.
    document.addEventListener("resonance:consent", (event) => {
      onConsentState(event.detail?.shared === true);
    });
    // An agent can run a discovery through the WebMCP tools without touching
    // this page. The results on screen would then be the previous answer, so
    // the transport says when it has run one and the page re-reads.
    document.addEventListener("resonance:discovered", () => { loadResults(); });
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
