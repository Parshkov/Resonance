const DISCOVERY_CONTRACT = "resonance-discovery/0.1";
const CONTEXT_CONTRACT = "resonance-ui-context/0.1";
const CANONICAL_MODE = "analogical";
const CANONICAL_K = 15;
const PRIMARY_CLASSIFICATION = "analogical";
const PRIMARY_LIMIT = 4;
const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
  source: "replay",
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
  const selected = [];
  for (const match of payload.matches) {
    if (!isDiscoverable(match)) continue;
    if (match.hard_rejection !== null) continue;
    if (match.mode_classification !== PRIMARY_CLASSIFICATION) continue;
    selected.push(match);
    if (selected.length === PRIMARY_LIMIT) break;
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

export function mapPoint(location) {
  return {
    x: ((location.lon + 180) / 360) * 1000,
    y: ((90 - location.lat) / 180) * 500,
  };
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
  document.getElementById(id).textContent = value;
}

function formatScore(value) {
  return Number(value).toFixed(4);
}

function shortSnapshot(value) {
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function placeLabel(location) {
  if (!location) return "Location not shared";
  return `${location.city} · ${location.region}`;
}

function renderContext(context) {
  const thought = context.active_thought;
  const nodes = thought.nodes;
  const topic = context.presentation?.topic || nodes[0]?.label || "Shared thought";
  const mechanism = nodes.find((node) => node.role === "mechanism")?.label || nodes[1]?.label;
  const outcome = nodes.find((node) => node.role === "outcome")?.label || nodes[2]?.label;
  const method = nodes.find((node) => node.role === "method")?.label;

  setText("thought-id", thought.thought_id);
  const title = document.getElementById("thought-heading");
  title.replaceChildren();
  title.append(document.createTextNode(topic));
  if (mechanism) {
    title.append(el("span", "chain-arrow", " → "));
    title.append(document.createTextNode(mechanism));
  }
  setText("thought-caption", thought.source?.text || "Accepted shared context.");
  setText("user-message", `I keep seeing ${nodes[0]?.label} trigger ${mechanism}, until ${outcome || "the system destabilizes"}. Could ${method || "a control loop"} interrupt it?`);
  setText("agent-message", "Shared with Resonance. I’ll compare only the consented structural trace and coarse synthetic location.");

  const consent = document.getElementById("header-consent");
  consent.replaceChildren(el("span", "status-light"), el("span", "", "Shared with Resonance"));

  const chain = document.getElementById("dna-chain");
  chain.replaceChildren();
  const chainNodes = nodes.slice(0, 5);
  chainNodes.forEach((node, index) => {
    const row = el("div", "dna-node");
    row.append(el("strong", "", node.label), el("span", "", node.role));
    chain.append(row);
    if (index < chainNodes.length - 1) chain.append(el("div", "dna-arrow"));
  });

  const declared = document.getElementById("declared-context");
  declared.replaceChildren();
  const contextValues = [
    ["Domain", context.presentation?.domain || "Not shared"],
    ["Coarse location", context.location ? `${context.location.city} · ${context.location.region}` : "Not shared"],
  ];
  for (const [label, value] of contextValues) {
    const item = el("div", "context-item");
    item.append(el("span", "", label), el("strong", "", value));
    declared.append(item);
  }
  setText("request-mode", context.pinned_request.mode);
  setText("request-k", `k=${context.pinned_request.k}`);
}

function firstCorrespondence(match) {
  const correspondence = match.evidence.top_correspondences[0];
  if (!correspondence) return "Evidence mapping available";
  return `${correspondence.query_label} ↔ ${correspondence.candidate_label}`;
}

function renderMatches(payload, primary) {
  const list = document.getElementById("match-list");
  list.replaceChildren();
  primary.forEach((match, index) => {
    const button = el("button", "match-card");
    button.type = "button";
    button.dataset.sessionId = match.session_id;
    button.dataset.backendScore = String(match.scores.structural);
    button.dataset.backendClassification = match.mode_classification;
    button.setAttribute("aria-pressed", String(match.session_id === state.selectedSessionId));
    button.setAttribute("aria-label", `Open evidence for ${match.person_pseudonym}: ${match.display.topic}`);

    const number = el("span", "match-card__index", String(index + 1).padStart(2, "0"));
    const body = el("div", "match-card__body");
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
      el("span", "location", placeLabel(match.display.location)),
    );
    body.append(top, topic, why, meta);
    button.append(number, body);
    button.addEventListener("click", () => selectMatch(match.session_id));
    list.append(button);
  });
  setText("shown-count", `${String(primary.length).padStart(2, "0")} shown`);
  setText("response-summary", `${payload.matches.length} matches · ${payload.rejected.length} rejected`);
}

function renderEvidence(match) {
  setText("evidence-kicker", `Why ${match.person_pseudonym} resonates`);
  setText("evidence-heading", match.display.topic);
  setText("evidence-subtitle", `${match.display.domain} · ${placeLabel(match.display.location)}`);
  setText("metric-class", match.mode_classification);
  setText("metric-structural", formatScore(match.scores.structural));
  setText("metric-confidence", match.confidence);

  const mappings = document.getElementById("mapping-list");
  mappings.replaceChildren();
  match.evidence.top_correspondences.slice(0, 4).forEach((mapping) => {
    const row = el("div", "mapping-row");
    const query = el("div", "mapping-side");
    query.append(el("small", "", mapping.query_node), el("strong", "", mapping.query_label));
    const candidate = el("div", "mapping-side");
    candidate.append(el("small", "", mapping.candidate_node), el("strong", "", mapping.candidate_label));
    row.append(query, el("div", "mapping-arrow", "↔"), candidate);
    mappings.append(row);
  });

  const relations = document.getElementById("relation-chips");
  relations.replaceChildren();
  match.evidence.preserved_relations.slice(0, 5).forEach((relation) => {
    relations.append(el("span", "relation-chip", `${relation.query_relation} ↔ ${relation.candidate_relation}`));
  });
  setText(
    "proof-note",
    `${match.evidence.mapped_node_count} mapped nodes · ${match.evidence.preserved_relation_count} preserved · ${match.evidence.contradiction_count} contradictions. Backend evidence, presented unchanged.`,
  );
}

function connectionPath(from, to, rejected = false) {
  const bend = rejected ? 28 : -34;
  const middleX = (from.x + to.x) / 2;
  const middleY = (from.y + to.y) / 2 + bend;
  return `M${from.x.toFixed(1)} ${from.y.toFixed(1)} Q${middleX.toFixed(1)} ${middleY.toFixed(1)} ${to.x.toFixed(1)} ${to.y.toFixed(1)}`;
}

function addConnection(layer, from, to, sessionId, rejected = false) {
  const path = svgEl("path", {
    d: connectionPath(from, to, rejected),
    class: `connection-line${rejected ? " is-rejected" : ""}`,
    "data-session-id": sessionId,
  });
  layer.append(path);
}

function addMarker(layer, location, options) {
  const point = mapPoint(location);
  const marker = svgEl("g", {
    class: `marker ${options.kind}`,
    transform: `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`,
    "data-session-id": options.sessionId,
    "aria-label": options.ariaLabel,
  });
  if (options.selectable) {
    marker.setAttribute("role", "button");
    marker.setAttribute("tabindex", "0");
    marker.addEventListener("click", () => selectMatch(options.sessionId));
    marker.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectMatch(options.sessionId);
      }
    });
  }
  marker.append(
    svgEl("circle", {class: "marker-halo", r: options.radius + 7}),
    svgEl("circle", {class: "marker-ring", r: options.radius}),
    svgEl("circle", {class: "marker-core", r: 2.4}),
  );
  if (options.index) {
    const index = svgEl("text", {class: "marker-index", y: -0.5});
    index.textContent = options.index;
    marker.append(index);
  }
  const label = svgEl("text", {class: "marker-label", y: options.radius + 16});
  label.textContent = options.label;
  marker.append(label);
  layer.append(marker);
}

function renderMap(context, payload, primary, others, rejected) {
  const connections = document.getElementById("connection-layer");
  const markers = document.getElementById("marker-layer");
  connections.replaceChildren();
  markers.replaceChildren();

  const queryLocation = context.location;
  const queryPoint = queryLocation ? mapPoint(queryLocation) : null;
  if (queryLocation) {
    addMarker(markers, queryLocation, {
      kind: "is-query",
      sessionId: "active-thought",
      ariaLabel: `Active thought at ${placeLabel(queryLocation)}`,
      label: "Active thought",
      radius: 13,
      selectable: false,
    });
  }

  let unlocatedPrimary = null;
  primary.forEach((match, index) => {
    if (!match.display.location) {
      unlocatedPrimary ||= match;
      return;
    }
    const point = mapPoint(match.display.location);
    if (queryPoint) addConnection(connections, queryPoint, point, match.session_id);
    addMarker(markers, match.display.location, {
      kind: "is-primary",
      sessionId: match.session_id,
      ariaLabel: `${match.person_pseudonym}, ${placeLabel(match.display.location)}`,
      label: match.person_pseudonym,
      index: String(index + 1),
      radius: 11,
      selectable: true,
    });
  });

  others.forEach((match) => {
    if (!match.display.location) return;
    addMarker(markers, match.display.location, {
      kind: "is-other",
      sessionId: match.session_id,
      ariaLabel: `Other returned match: ${match.person_pseudonym}`,
      label: "",
      radius: 6,
      selectable: false,
    });
  });

  rejected.forEach((match) => {
    if (!match.display.location) return;
    const point = mapPoint(match.display.location);
    if (queryPoint) addConnection(connections, queryPoint, point, match.session_id, true);
    addMarker(markers, match.display.location, {
      kind: "is-rejected",
      sessionId: match.session_id,
      ariaLabel: `Rejected contradiction: ${match.person_pseudonym}`,
      label: "",
      radius: 7,
      selectable: false,
    });
  });

  const unlocated = document.getElementById("unlocated-anchor");
  unlocated.hidden = !unlocatedPrimary;
  if (unlocatedPrimary) setText("unlocated-name", unlocatedPrimary.person_pseudonym);
  setText("map-status-text", `${primary.length} flagship analogies · backend order intact`);
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

function drawerRow(row, order, rejected = false) {
  const item = el("div", "drawer-row");
  item.dataset.sessionId = row.session_id;
  item.append(el("span", "drawer-row__order", String(order).padStart(2, "0")));
  const copy = el("div");
  copy.append(el("strong", "", `${row.person_pseudonym} · ${row.display.topic}`));
  copy.append(el("span", "", `${row.mode_classification} · ${placeLabel(row.display.location)}`));
  item.append(copy, el("code", "", rejected ? row.hard_rejection : formatScore(row.scores.structural)));
  return item;
}

function renderDrawer(others, rejected) {
  setText("secondary-count", String(others.length + rejected.length));
  const trigger = document.getElementById("secondary-trigger");
  trigger.disabled = others.length + rejected.length === 0;

  const matches = document.getElementById("drawer-matches");
  const rejectedList = document.getElementById("drawer-rejected");
  matches.replaceChildren();
  rejectedList.replaceChildren();
  others.forEach((match, index) => matches.append(drawerRow(match, index + 1)));
  rejected.forEach((match, index) => rejectedList.append(drawerRow(match, index + 1, true)));
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

function renderDiscovery(payload) {
  const primary = selectPrimaryMatches(payload);
  if (!primary.length) throw new Error("No eligible analogical matches were returned");
  state.payload = payload;
  state.primary = primary;
  state.selectedSessionId = primary[0].session_id;
  const others = visibleOtherMatches(payload, primary);
  const rejected = visibleRejected(payload);

  renderMatches(payload, primary);
  renderMap(state.context, payload, primary, others, rejected);
  renderContradictions(rejected);
  renderDrawer(others, rejected);
  renderEvidence(primary[0]);
  updateSelection();

  const snapshot = payload.query.provenance.corpus_snapshot;
  setText("snapshot-short", shortSnapshot(snapshot));
  const button = document.getElementById("snapshot-button");
  button.disabled = false;
  button.title = snapshot;
  setText("source-note", state.source === "live"
    ? "LIVE · accepted discover_resonance MCP path · analogical / k=15"
    : "REPLAY · genuine accepted R8 fixture · analogical / k=15");
  setText("runtime-badge", state.source === "live" ? "Accepted MCP · local" : "Deterministic · offline");
  document.getElementById("app-shell").dataset.state = "ready";
}

function setSourceControls(source, loading = false) {
  document.querySelectorAll(".source-option").forEach((button) => {
    const active = button.dataset.source === source;
    button.classList.toggle("is-active", active);
    button.classList.toggle("is-loading", active && loading);
    button.setAttribute("aria-pressed", String(active));
    button.disabled = loading;
  });
  document.getElementById("map-status").classList.toggle("is-loading", loading);
  if (loading) setText("map-status-text", source === "live" ? "Calling accepted discovery MCP…" : "Loading accepted replay fixture…");
}

function showError(error) {
  document.getElementById("app-shell").dataset.state = "error";
  setText("map-status-text", `Discovery unavailable: ${error.message}`);
  setText("source-note", "No results rendered · accepted source validation failed closed");
  setSourceControls(state.source, false);
}

async function loadSource(source) {
  state.source = source;
  setSourceControls(source, true);
  const url = new URL(window.location.href);
  url.searchParams.set("source", source);
  window.history.replaceState({}, "", url);
  try {
    const response = await fetch(`/api/discover?source=${encodeURIComponent(source)}`, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    assertAcceptedDiscovery(payload);
    renderDiscovery(payload);
    setSourceControls(source, false);
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
}

let toastTimer;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 1800);
}

async function copySnapshot() {
  const snapshot = state.payload?.query?.provenance?.corpus_snapshot;
  if (!snapshot) return;
  try {
    await navigator.clipboard.writeText(snapshot);
    showToast("Corpus snapshot copied");
  } catch {
    showToast(`Snapshot ${shortSnapshot(snapshot)}`);
  }
}

async function boot() {
  try {
    const [configResponse, contextResponse] = await Promise.all([
      fetch("/api/config", {cache: "no-store"}),
      fetch("/api/context", {cache: "no-store"}),
    ]);
    if (!configResponse.ok || !contextResponse.ok) throw new Error("Presentation context is unavailable");
    const config = await configResponse.json();
    const context = await contextResponse.json();
    assertAcceptedContext(context);
    state.context = context;
    renderContext(context);

    document.querySelectorAll(".source-option").forEach((button) => {
      button.addEventListener("click", () => loadSource(button.dataset.source));
    });
    document.getElementById("secondary-trigger").addEventListener("click", () => setDrawer(true));
    document.getElementById("drawer-close").addEventListener("click", () => setDrawer(false));
    document.getElementById("drawer-backdrop").addEventListener("click", () => setDrawer(false));
    document.getElementById("snapshot-button").addEventListener("click", copySnapshot);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setDrawer(false);
    });

    const requested = new URL(window.location.href).searchParams.get("source");
    const source = requested === "live" || requested === "replay" ? requested : config.default_source;
    await loadSource(source);
  } catch (error) {
    showError(error);
  }
}

if (typeof document !== "undefined") boot();
