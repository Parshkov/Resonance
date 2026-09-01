const MAP_LAND = [
  [80,120,220,150,310,180,360,140,420,170,480,130,520,160,580,120,620,90,80,90],
  [120,260,210,240,280,270,360,250,430,280,500,260,560,290,630,270,700,300,120,320],
  [640,180,720,160,800,190,860,170,920,200,880,240,790,230,700,220]
];

function project(lat, lon) {
  return [((lon + 180) / 360) * 1000, ((90 - lat) / 180) * 560];
}

function el(tag, attrs, text) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
  if (text != null) node.textContent = text;
  return node;
}

function drawMap(view) {
  const svg = document.getElementById("map");
  svg.innerHTML = "";
  MAP_LAND.forEach((pts) => {
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    const pairs = [];
    for (let i = 0; i < pts.length; i += 2) pairs.push(pts[i] + "," + pts[i + 1]);
    poly.setAttribute("points", pairs.join(" "));
    poly.setAttribute("class", "land");
    svg.appendChild(poly);
  });
  (view.markers || []).forEach((m) => {
    const [x, y] = project(m.lat, m.lon);
    const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    c.setAttribute("cx", x);
    c.setAttribute("cy", y);
    c.setAttribute("r", m.kind === "featured" ? 9 : 6);
    c.setAttribute("class", "pulse " + m.kind);
    svg.appendChild(c);
  });
}

function render(view) {
  document.getElementById("mode-indicator").textContent = view.mode_indicator;
  document.getElementById("pin-label").textContent =
    view.pinned.mode + " · k=" + view.pinned.k;
  document.getElementById("consent").textContent = view.query.share_state;
  document.getElementById("query-name").textContent = view.query.person_pseudonym;
  document.getElementById("query-topic").textContent =
    view.query.topic + " · " + view.query.domain;
  const loc = view.query.location;
  document.getElementById("query-place").textContent = loc.city + " · " + loc.region;
  const thread = document.getElementById("thread");
  thread.innerHTML = "";
  view.query.conversation.forEach((turn) => {
    const b = el("div", {class: "bubble"});
    b.appendChild(el("b", {}, turn.who + " · "));
    b.appendChild(document.createTextNode(turn.text));
    thread.appendChild(b);
  });
  const dna = document.getElementById("dna");
  dna.innerHTML = "";
  view.query.nodes.forEach((n) => dna.appendChild(el("span", {class: "chip"}, n.role + ": " + n.label)));
  const cards = document.getElementById("cards");
  cards.innerHTML = "";
  view.featured.forEach((card, idx) => {
    const btn = el("button", {class: "card", "data-id": card.session_id});
    const score = card.structural;
    const city = (card.location && card.location.city) || "location withheld";
    btn.appendChild(el("div", {class: "who"},
      (idx + 1) + ". " + card.person_pseudonym + " · " + card.mode_classification + " · S=" + score));
    btn.appendChild(el("div", {class: "why"},
      card.domain + " · " + city + " · " + card.why));
    btn.addEventListener("click", () => showDetail(card, btn));
    cards.appendChild(btn);
  });
  const other = document.getElementById("other");
  other.innerHTML = "";
  view.other_matches.forEach((m) => {
    other.appendChild(el("li", {},
      m.person_pseudonym + " · " + m.mode_classification + " · S=" + m.structural));
  });
  const rejected = document.getElementById("rejected");
  rejected.innerHTML = "";
  view.contradictions.forEach((m) => {
    rejected.appendChild(el("li", {},
      m.person_pseudonym + " · contradiction · " + (m.hard_rejection || "hard_rejection")));
  });
  const buckets = ((view.aggregation || {}).buckets || [])
    .map((b) => b.bucket_id + " " + b.count).join(" · ");
  document.getElementById("agg").textContent =
    "Aggregation over discoverable shareable locations only: " + buckets;
  drawMap(view);
}

function showDetail(card, btn) {
  document.querySelectorAll(".card").forEach((n) => n.classList.remove("active"));
  btn.classList.add("active");
  const box = document.getElementById("detail");
  box.classList.remove("hidden");
  const ev = card.evidence || {};
  const pairs = (ev.top_correspondences || []).map((row) =>
    '<div class="pair">' + row.query_label + " → " + row.candidate_label + "</div>"
  ).join("");
  box.innerHTML =
    "<h3>" + card.person_pseudonym + " · " + card.mode_classification + "</h3>" +
    "<p>Scores copied from backend. structural=" + card.structural +
    " · semantic=" + card.scores.semantic +
    " · mapped=" + ev.mapped_node_count +
    " · preserved=" + ev.preserved_relation_count + "</p>" +
    '<div class="pairs">' + pairs + "</div>";
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const path = params.get("source") === "live" ? "/api/live" : "/api/replay";
  const view = await fetch(path).then((r) => r.json());
  render(view);
}

boot();
