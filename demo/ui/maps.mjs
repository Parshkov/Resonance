/**
 * Two maps of the people found for a thought.
 *
 * The resonance map: your thought at the centre, every person placed by how
 * closely their reasoning matches (the inner ring is a perfect match, the rim
 * is none), grouped by the kind of match. Nothing is ranked here: the radius
 * is the engine's structural score, drawn.
 *
 * The world map: the coarse places people agreed to share (a city rounded to
 * a tenth of a degree), on a deliberately blunt sketch of the continents.
 * Where someone is never affects whether they are found.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

// ---- the resonance map ------------------------------------------------------

const RING_STEPS = [1.0, 0.75, 0.5, 0.25];
const KIND_ORDER = ["direct", "approximate", "analogical", "complementary", "negative"];

export function resonanceMap(items, {selected = null, onSelect = null, kindLabel = (k) => k} = {}) {
  const size = 520, cx = size / 2, cy = size / 2, R = size / 2 - 40, r0 = R * 0.12;
  const svg = svgEl("svg", {class: "rmap", viewBox: `0 0 ${size} ${size}`, role: "img"});
  const title = svgEl("title"); title.textContent = "How closely each person's reasoning matches yours";
  svg.append(title);
  for (const step of RING_STEPS) {
    const radius = r0 + (R - r0) * (1 - step);
    svg.append(svgEl("circle", {cx, cy, r: radius, class: "rmap__ring"}));
    // Ring labels climb the vertical axis, where no person is drawn (the
    // first sector starts at twelve o'clock), so they never sit on a name.
    const label = svgEl("text", {x: cx + 5, y: cy - radius - 3, class: "rmap__ring-label"});
    label.textContent = step.toFixed(2);
    svg.append(label);
  }
  // sectors by kind of match, in a fixed order, sized by how many are in each
  const groups = new Map();
  for (const item of items) {
    const kind = KIND_ORDER.includes(item.kind) ? item.kind : "negative";
    if (!groups.has(kind)) groups.set(kind, []);
    groups.get(kind).push(item);
  }
  const present = KIND_ORDER.filter((k) => groups.has(k));
  const gap = present.length > 1 ? 8 : 0;
  const usable = 360 - gap * present.length;
  let angle = -90;
  const legend = [];
  for (const kind of present) {
    const members = groups.get(kind);
    const span = present.length === 1 ? 360 : usable * (members.length / items.length);
    if (present.length > 1) {
      const a0 = angle * Math.PI / 180, a1 = (angle + span) * Math.PI / 180;
      const large = span > 180 ? 1 : 0;
      svg.append(svgEl("path", {class: `rmap__sector rmap__sector--${kind}`,
        d: `M${cx} ${cy} L${cx + R * Math.cos(a0)} ${cy + R * Math.sin(a0)} A${R} ${R} 0 ${large} 1 ${cx + R * Math.cos(a1)} ${cy + R * Math.sin(a1)} Z`}));
    }
    members.forEach((item, index) => {
      const theta = (angle + span * ((index + 0.5) / members.length)) * Math.PI / 180;
      const radius = r0 + (R - r0) * (1 - Math.max(0, Math.min(1, item.strength)));
      const x = cx + radius * Math.cos(theta), y = cy + radius * Math.sin(theta);
      svg.append(svgEl("line", {x1: cx, y1: cy, x2: x, y2: y, class: `rmap__link ${item.contradictions ? "is-dashed" : ""}`,
        "stroke-width": String(1 + Math.min(4, item.links || 0))}));
      const dot = svgEl("g", {class: `rmap__person ${item.id === selected ? "is-selected" : ""}`, tabindex: "0", role: "button"});
      dot.append(svgEl("circle", {cx: x, cy: y, r: 14, class: "rmap__hit"}));
      dot.append(svgEl("circle", {cx: x, cy: y, r: 7, class: `rmap__dot rmap__dot--${kind}`}));
      const name = svgEl("text", {x: x + 11, y: y + 4, class: "rmap__name"});
      name.textContent = item.name;
      dot.append(name);
      const hint = svgEl("title"); hint.textContent = `${item.name} · ${item.topic || ""} · ${item.strength.toFixed(2)}`;
      dot.append(hint);
      if (onSelect) {
        dot.addEventListener("click", () => onSelect(item.id));
        dot.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(item.id); } });
      }
      svg.append(dot);
    });
    legend.push({kind, count: members.length, label: kindLabel(kind)});
    angle += span + gap;
  }
  svg.append(svgEl("circle", {cx, cy, r: 9, class: "rmap__you"}));
  const you = svgEl("text", {x: cx, y: cy + 24, class: "rmap__you-label", "text-anchor": "middle"});
  you.textContent = "your thought";
  svg.append(you);
  return {svg, legend};
}

// ---- the world map --------------------------------------------------------------

// Plate carrée at one scale in both directions. Everything above 84° and
// below 60° south is ice and empty water.
const MAP_WIDTH = 1000;
const TOP_LAT = 84;
const BOTTOM_LAT = -60;
const MAP_HEIGHT = Math.round(MAP_WIDTH / 360 * (TOP_LAT - BOTTOM_LAT));
const SAME_SPOT_STEPS = [[-13, 0], [0, -13], [0, 13], [-10, -10], [-10, 10], [-24, 0]];

export function project(lat, lon) {
  const x = (Number(lon) + 180) / 360 * MAP_WIDTH;
  const y = (TOP_LAT - Number(lat)) / (TOP_LAT - BOTTOM_LAT) * MAP_HEIGHT;
  return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
}

// Outlines as [longitude, latitude] corners, deliberately blunt: a location
// on this map is a city rounded to ten kilometres.
const LAND = [
  // North America, Central America to Panama.
  [[-168, 66], [-162, 70], [-141, 70], [-128, 70], [-115, 73], [-95, 74], [-80, 73], [-72, 68],
   [-66, 60], [-60, 56], [-56, 52], [-60, 47], [-66, 44], [-70, 42], [-74, 40], [-76, 36],
   [-80, 32], [-81, 27], [-80, 25], [-82, 28], [-85, 30], [-90, 29], [-94, 29], [-97, 26],
   [-97, 21], [-91, 19], [-88, 21], [-87, 17], [-84, 13], [-83, 10], [-80, 8], [-78, 8],
   [-83, 8], [-86, 12], [-90, 14], [-95, 16], [-105, 20], [-106, 23], [-110, 25], [-112, 29],
   [-115, 32], [-118, 34], [-121, 37], [-124, 41], [-124, 47], [-127, 51], [-132, 55],
   [-137, 58], [-141, 60], [-146, 61], [-152, 59], [-158, 57], [-163, 55], [-166, 60],
   [-162, 64]],
  // Greenland.
  [[-73, 78], [-60, 82], [-40, 83], [-20, 82], [-18, 76], [-22, 70], [-30, 68], [-42, 60],
   [-48, 62], [-53, 67], [-56, 72], [-62, 76]],
  // South America.
  [[-78, 8], [-72, 12], [-64, 11], [-60, 8], [-52, 4], [-50, 0], [-44, -2], [-38, -4], [-35, -8],
   [-38, -13], [-39, -18], [-42, -23], [-48, -26], [-49, -29], [-53, -34], [-58, -38], [-62, -39],
   [-65, -42], [-65, -46], [-68, -50], [-68, -53], [-66, -55], [-71, -54], [-75, -50], [-74, -45],
   [-73, -40], [-71, -33], [-70, -25], [-70, -18], [-76, -14], [-79, -8], [-81, -5], [-80, 0],
   [-77, 4]],
  // Europe and Asia as one landmass, Arabia and India included.
  [[-9, 43], [-9, 37], [-6, 36], [-2, 37], [0, 39], [3, 43], [5, 43], [8, 44], [10, 44], [12, 42],
   [14, 41], [16, 38], [18, 40], [16, 42], [13, 45], [14, 45], [16, 43], [19, 42], [20, 40],
   [22, 37], [24, 38], [23, 40], [26, 41], [28, 41], [26, 40], [27, 37], [30, 36], [36, 36],
   [35, 33], [34, 31], [33, 30], [34, 28], [35, 26], [38, 22], [40, 19], [43, 13], [45, 13],
   [49, 14], [53, 17], [57, 19], [59, 22], [58, 24], [56, 26], [54, 25], [51, 24], [50, 27],
   [48, 30], [50, 30], [54, 27], [57, 26], [61, 25], [66, 25], [68, 24], [70, 21], [72, 20],
   [73, 16], [76, 10], [78, 8], [80, 12], [80, 15], [82, 17], [85, 20], [88, 22], [91, 22],
   [92, 21], [94, 16], [97, 10], [98, 8], [100, 5], [103, 1], [104, 3], [103, 7], [100, 13],
   [105, 9], [107, 10], [109, 12], [108, 17], [106, 20], [108, 21], [112, 21], [115, 23],
   [119, 25], [121, 28], [122, 31], [120, 35], [122, 37], [119, 38], [118, 39], [121, 40],
   [125, 40], [126, 37], [127, 35], [129, 36], [130, 38], [131, 43], [135, 44], [138, 47],
   [140, 50], [141, 52], [143, 54], [139, 54], [136, 56], [141, 59], [151, 59], [156, 61],
   [160, 60], [164, 60], [170, 60], [176, 63], [180, 65], [180, 69], [176, 70], [170, 70],
   [164, 69], [160, 71], [150, 72], [140, 73], [130, 71], [120, 73], [110, 74], [100, 77],
   [90, 76], [80, 73], [73, 70], [68, 69], [62, 69], [58, 70], [52, 68], [45, 68], [40, 66],
   [35, 67], [33, 69], [30, 70], [26, 71], [20, 70], [15, 68], [12, 65], [8, 63], [5, 62],
   [5, 59], [7, 58], [10, 57], [8, 57], [8, 55], [7, 54], [5, 53], [4, 52], [2, 51], [0, 50],
   [-2, 49], [-5, 49], [-4, 48], [-2, 47], [-1, 46], [-2, 44]],
  // Africa.
  [[-17, 21], [-17, 15], [-16, 12], [-13, 8], [-8, 5], [-4, 5], [0, 6], [5, 4], [9, 4], [10, 2],
   [9, -1], [12, -6], [13, -12], [12, -17], [14, -23], [15, -28], [18, -33], [20, -35], [26, -34],
   [31, -30], [33, -26], [35, -24], [40, -15], [40, -10], [39, -6], [40, -3], [42, 0], [46, 4],
   [51, 11], [43, 12], [42, 14], [39, 17], [37, 21], [34, 25], [33, 28], [32, 31], [25, 32],
   [20, 31], [16, 32], [11, 34], [10, 37], [3, 37], [0, 36], [-3, 35], [-6, 35], [-10, 30],
   [-14, 26]],
  // Australia.
  [[114, -22], [114, -28], [115, -34], [118, -35], [124, -33], [129, -32], [132, -32], [136, -35],
   [138, -35], [140, -38], [147, -39], [150, -37], [152, -33], [153, -28], [152, -24], [149, -21],
   [146, -19], [145, -15], [143, -11], [141, -13], [137, -12], [136, -14], [132, -12], [130, -13],
   [126, -14], [122, -18], [118, -20]],
  // Islands large enough to matter at this scale.
  [[-5, 50], [0, 51], [2, 53], [0, 54], [-2, 56], [-3, 58], [-6, 58], [-5, 55], [-3, 54], [-5, 52]],
  [[-10, 52], [-6, 52], [-6, 54], [-8, 55], [-10, 54]],
  [[-24, 65], [-20, 66], [-15, 66], [-14, 64], [-20, 63]],
  [[11, 79], [20, 80], [27, 79], [20, 77], [15, 77]],
  [[130, 31], [131, 34], [135, 34], [137, 35], [140, 35], [141, 38], [141, 41], [140, 42],
   [142, 44], [145, 44], [144, 42], [140, 41], [139, 38], [136, 37], [133, 36]],
  [[44, -25], [47, -25], [50, -16], [49, -12], [47, -15], [44, -18]],
  [[80, 6], [82, 7], [81, 9], [80, 9]],
  [[95, 5], [98, 4], [102, 0], [106, -5], [104, -6], [100, -3], [97, 1]],
  [[105, -6], [110, -6], [114, -8], [112, -8], [106, -7]],
  [[109, 1], [111, 3], [115, 5], [117, 7], [119, 4], [118, 1], [116, -3], [114, -4], [110, -3],
   [109, 0]],
  [[120, 18], [122, 18], [123, 13], [126, 8], [125, 6], [122, 8], [121, 13]],
  [[131, -1], [135, -3], [141, -3], [147, -6], [150, -10], [146, -9], [141, -9], [138, -8],
   [134, -4]],
  [[145, -41], [148, -41], [147, -43], [145, -43]],
  [[167, -46], [170, -46], [173, -43], [174, -41], [175, -39], [178, -38], [174, -35], [173, -37],
   [175, -40], [171, -42]],
  [[-85, 22], [-80, 23], [-75, 20], [-77, 20], [-82, 22]],
];

const INLAND_WATER = [
  // Hudson Bay, the Baltic, the Black Sea, the Caspian.
  [[-95, 61], [-88, 57], [-82, 53], [-79, 52], [-77, 56], [-78, 62], [-85, 64], [-93, 64]],
  [[10, 54], [14, 54], [20, 55], [21, 57], [24, 59], [28, 60], [30, 60], [26, 61], [22, 62],
   [21, 64], [25, 66], [22, 66], [19, 63], [18, 60], [16, 57], [12, 56]],
  [[28, 41], [31, 41], [36, 42], [41, 41], [40, 44], [37, 45], [33, 45], [31, 46], [29, 45],
   [28, 43]],
  [[47, 43], [51, 46], [53, 44], [52, 40], [54, 37], [50, 37], [49, 40]],
];

function outlinePath(corners) {
  return corners.map(([lon, lat], index) => {
    const [x, y] = project(lat, lon);
    return `${index === 0 ? "M" : "L"}${x} ${y}`;
  }).join(" ") + " Z";
}

export function worldMap(geo, {selected = null, onSelect = null} = {}) {
  const svg = svgEl("svg", {class: "wmap", viewBox: `0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`, role: "img"});
  const title = svgEl("title"); title.textContent = "Where the people who shared a location are, roughly";
  svg.append(title);
  const land = svgEl("g", {class: "wmap__land"});
  for (const corners of LAND) land.append(svgEl("path", {class: "wmap__ground", d: outlinePath(corners)}));
  for (const corners of INLAND_WATER) land.append(svgEl("path", {class: "wmap__water", d: outlinePath(corners)}));
  svg.append(land);
  const taken = new Map();
  const spot = (lat, lon) => {
    let [x, y] = project(lat, lon);
    const key = `${x},${y}`;
    const n = taken.get(key) || 0;
    taken.set(key, n + 1);
    if (n > 0) { const [dx, dy] = SAME_SPOT_STEPS[(n - 1) % SAME_SPOT_STEPS.length]; x += dx; y += dy; }
    return [x, y];
  };
  const placed = [], unplaced = [];
  if (geo?.you?.place) {
    const [x, y] = spot(geo.you.lat, geo.you.lon);
    svg.append(svgEl("circle", {cx: x, cy: y, r: 8, class: "wmap__you"}));
    const label = svgEl("text", {x: x + 11, y: y + 4, class: "wmap__name"}); label.textContent = "you";
    svg.append(label);
  } else if (geo?.you && Number.isFinite(geo.you.lat)) {
    const [x, y] = spot(geo.you.lat, geo.you.lon);
    svg.append(svgEl("circle", {cx: x, cy: y, r: 8, class: "wmap__you"}));
  }
  for (const person of geo?.people || []) {
    if (!person.place || !Number.isFinite(person.place.lat)) { unplaced.push(person); continue; }
    const [x, y] = spot(person.place.lat, person.place.lon);
    const g = svgEl("g", {class: `wmap__person ${person.session_id === selected ? "is-selected" : ""} ${person.resonance ? "" : "is-faint"}`, tabindex: "0", role: "button"});
    g.append(svgEl("circle", {cx: x, cy: y, r: 14, class: "wmap__hit"}));
    g.append(svgEl("circle", {cx: x, cy: y, r: 6, class: "wmap__dot"}));
    const label = svgEl("text", {x: x + 10, y: y + 4, class: "wmap__name"}); label.textContent = person.name;
    g.append(label);
    const hint = svgEl("title"); hint.textContent = `${person.name} · ${person.place.city}, ${person.place.region}${person.about_km ? ` · about ${person.about_km} km from you` : ""}`;
    g.append(hint);
    if (onSelect) g.addEventListener("click", () => onSelect(person.session_id));
    svg.append(g);
    placed.push(person);
  }
  return {svg, placed, unplaced};
}

// ---- the constellation ----------------------------------------------------------
//
// Every thought of yours is a centre; every person found is a body drawn
// towards the thoughts they resonate with. The pull is the structural score
// (a strong match sits close), the size is the depth of the match (how many
// of your ideas theirs answers), and the colour is the kind of match. A
// small force layout places them; nothing is ranked here, only placed.

function forceLayout(nodes, links, {width, height, iterations = 260} = {}) {
  const cx = width / 2, cy = height / 2;
  nodes.forEach((n, i) => {
    if (n.fixed) return;
    const a = (i / Math.max(1, nodes.length)) * Math.PI * 2;
    n.x = cx + Math.cos(a) * width * 0.3; n.y = cy + Math.sin(a) * height * 0.3;
    n.vx = 0; n.vy = 0;
  });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  let alpha = 1;
  for (let step = 0; step < iterations; step += 1) {
    // repulsion
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i], b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx * dx + dy * dy || 0.01;
        const min = (a.r + b.r + 18);
        const d = Math.sqrt(d2);
        const force = (d < min ? (min - d) * 0.6 : 900 / d2) * alpha;
        const fx = dx / d * force, fy = dy / d * force;
        if (!a.fixed) { a.vx -= fx; a.vy -= fy; }
        if (!b.fixed) { b.vx += fx; b.vy += fy; }
      }
    }
    // springs: rest length shrinks with strength
    for (const l of links) {
      const a = byId.get(l.source), b = byId.get(l.target);
      if (!a || !b) continue;
      const rest = 60 + (1 - l.strength) * 220;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const force = (d - rest) * 0.05 * alpha;
      const fx = dx / d * force, fy = dy / d * force;
      if (!a.fixed) { a.vx += fx; a.vy += fy; }
      if (!b.fixed) { b.vx -= fx; b.vy -= fy; }
    }
    for (const n of nodes) {
      if (n.fixed) continue;
      n.vx += (cx - n.x) * 0.004 * alpha; n.vy += (cy - n.y) * 0.004 * alpha;
      n.x += n.vx; n.y += n.vy; n.vx *= 0.6; n.vy *= 0.6;
      n.x = Math.max(n.r + 8, Math.min(width - n.r - 8, n.x));
      n.y = Math.max(n.r + 8, Math.min(height - n.r - 8, n.y));
    }
    alpha = Math.max(0.05, alpha * 0.985);
  }
}

export function constellation({centres, people, links}, {selected = null, onSelect = null, kindLabel = (k) => k, width = 720, height = 460} = {}) {
  const nodes = [];
  const n = centres.length;
  centres.forEach((c, i) => {
    const angle = -Math.PI / 2 + (i / Math.max(1, n)) * Math.PI * 2;
    const spread = n > 1 ? Math.min(width, height) * 0.34 : 0;
    nodes.push({id: c.id, kind: "centre", label: c.label, r: 12, fixed: true,
      x: width / 2 + Math.cos(angle) * spread, y: height / 2 + Math.sin(angle) * spread});
  });
  for (const p of people) {
    const near = p.kind === "negative";
    nodes.push({id: p.id, kind: p.kind, label: p.name, r: near ? 4 : 7 + Math.min(10, p.depth * 2), strength: p.strength, topic: p.topic, depth: p.depth, links: p.links, near});
  }
  forceLayout(nodes, links, {width, height});
  const svg = svgEl("svg", {class: "cmap", viewBox: `0 0 ${width} ${height}`, role: "img"});
  const title = svgEl("title"); title.textContent = "Who resonates with which of your thoughts, and how closely";
  svg.append(title);
  const byId = new Map(nodes.map((nd) => [nd.id, nd]));
  for (const l of links) {
    const a = byId.get(l.source), b = byId.get(l.target);
    if (!a || !b) continue;
    const line = svgEl("line", {x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: `cmap__link cmap__link--${l.kind || "other"} ${l.contradictions ? "is-dashed" : ""}`,
      "stroke-width": String(1 + l.strength * 4), "stroke-opacity": String(0.25 + l.strength * 0.6)});
    line.dataset.person = l.target; line.dataset.centre = l.source;
    const hint = svgEl("title"); hint.textContent = `${b.label} ↔ ${a.label}: ${l.strength.toFixed(2)}`;
    line.append(hint);
    svg.append(line);
  }
  for (const nd of nodes) {
    const g = svgEl("g", {class: `cmap__node cmap__node--${nd.kind} ${nd.id === selected ? "is-selected" : ""}`, tabindex: nd.kind === "centre" ? "-1" : "0", role: nd.kind === "centre" ? "img" : "button"});
    g.dataset.id = nd.id;
    if (nd.kind === "centre") {
      g.append(svgEl("circle", {cx: nd.x, cy: nd.y, r: nd.r + 6, class: "cmap__halo"}));
      g.append(svgEl("circle", {cx: nd.x, cy: nd.y, r: nd.r, class: "cmap__centre"}));
    } else {
      g.append(svgEl("circle", {cx: nd.x, cy: nd.y, r: nd.r + 10, class: "cmap__hit"}));
      g.append(svgEl("circle", {cx: nd.x, cy: nd.y, r: nd.r, class: `cmap__dot cmap__dot--${nd.kind}`}));
    }
    if (!nd.near) {
      const label = svgEl("text", {x: nd.x + nd.r + 5, y: nd.y + 4, class: `cmap__name ${nd.kind === "centre" ? "cmap__name--centre" : ""}`});
      const most = nd.kind === "centre" ? 22 : 26;
      label.textContent = nd.label.length > most ? nd.label.slice(0, most - 1) + "…" : nd.label;
      g.append(label);
    }
    const hint = svgEl("title");
    hint.textContent = nd.kind === "centre" ? nd.label : `${nd.label} · ${nd.topic || ""} · ${(nd.strength || 0).toFixed(2)} · ${nd.depth} ideas correspond`;
    g.append(hint);
    if (onSelect && nd.kind !== "centre") {
      g.addEventListener("click", () => onSelect(nd.id));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(nd.id); } });
    }
    g.addEventListener("mouseenter", () => svg.querySelectorAll(`[data-person="${nd.id}"], [data-centre="${nd.id}"]`).forEach((l) => l.classList.add("is-hot")));
    g.addEventListener("mouseleave", () => svg.querySelectorAll(".is-hot").forEach((l) => l.classList.remove("is-hot")));
    svg.append(g);
  }
  return svg;
}

// ---- what corresponds, drawn -------------------------------------------------------
//
// Your ideas in a column on the left, theirs on the right, a line between
// each pair the engine put together. Links you both keep are drawn as arcs
// on your side; hovering an idea lights its counterpart and its links.

export function correspondence({mine, theirs, pairs, keptRelations = [], contradictions = []}, {width = 640} = {}) {
  const rowH = 34, top = 30, margin = 34;
  const rows = Math.max(mine.length, theirs.length, 1);
  const height = top + rows * rowH + 16;
  const leftX = margin, rightX = width - 12, colW = (width - margin - 12 - 60) / 2;
  const svg = svgEl("svg", {class: "corr", viewBox: `0 0 ${width} ${height}`, role: "img"});
  const title = svgEl("title"); title.textContent = "Which of their ideas answers which of yours";
  svg.append(title);
  const yOf = (i) => top + i * rowH + rowH / 2;
  const widthOf = (item) => Math.min(colW, 7.2 * Math.min(item.label.length, 34) + 20);
  const mineIndex = new Map(mine.map((m, i) => [m.id, i]));
  const theirsIndex = new Map(theirs.map((m, i) => [m.id, i]));
  const paired = new Map(pairs.map((p) => [p.mine, p.theirs]));
  const answered = new Set(paired.values());
  // Kept links: an arc between two of your ideas, in the margin to the left,
  // meaning the other person keeps this link between the same two ideas.
  for (const rel of keptRelations) {
    const a = mineIndex.get(rel.source), b = mineIndex.get(rel.target);
    if (a === undefined || b === undefined) continue;
    const y1 = yOf(a), y2 = yOf(b), x = leftX;
    const bend = Math.min(margin - 4, 12 + Math.abs(y2 - y1) * 0.25);
    const path = svgEl("path", {d: `M${x} ${y1} C${x - bend} ${y1}, ${x - bend} ${y2}, ${x} ${y2}`, class: "corr__kept"});
    path.dataset.nodes = `${rel.source} ${rel.target}`;
    const hint = svgEl("title"); hint.textContent = `${mine[a].label} ${String(rel.type || "").replace(/_/g, " ")} ${mine[b].label}: they keep this link too`;
    path.append(hint);
    svg.append(path);
  }
  // Correspondences: a curve from the right edge of your idea to the left
  // edge of theirs.
  for (const [mid, tid] of paired) {
    const a = mineIndex.get(mid), b = theirsIndex.get(tid);
    if (a === undefined || b === undefined) continue;
    const x1 = leftX + widthOf(mine[a]), x2 = rightX - widthOf(theirs[b]);
    const mid_x = (x1 + x2) / 2;
    const line = svgEl("path", {d: `M${x1} ${yOf(a)} C${mid_x} ${yOf(a)}, ${mid_x} ${yOf(b)}, ${x2} ${yOf(b)}`, class: "corr__pair"});
    line.dataset.nodes = `${mid} ${tid}`;
    const hint = svgEl("title"); hint.textContent = `${mine[a].label} ↔ ${theirs[b].label}`;
    line.append(hint);
    svg.append(line);
  }
  const contested = new Set(contradictions.flatMap((c) => [c.mine, c.theirs].filter(Boolean)));
  const column = (items, x, anchor, side) => items.forEach((item, i) => {
    const alone = side === "mine" ? !paired.has(item.id) : !answered.has(item.id);
    const g = svgEl("g", {class: `corr__idea corr__idea--${side} ${alone ? "is-alone" : ""} ${contested.has(item.id) ? "is-contested" : ""}`, tabindex: "0"});
    g.dataset.id = item.id;
    const w = widthOf(item);
    const bx = anchor === "start" ? x : x - w;
    g.append(svgEl("rect", {x: bx, y: yOf(i) - 13, width: w, height: 26, rx: 6, class: "corr__box"}));
    const text = svgEl("text", {x: bx + 10, y: yOf(i) + 4, class: "corr__label"});
    text.textContent = item.label.length > 34 ? item.label.slice(0, 33) + "…" : item.label;
    g.append(text);
    const hint = svgEl("title"); hint.textContent = alone ? `${item.label}: nothing on the other side answers this` : item.label;
    g.append(hint);
    const light = (on) => {
      const partner = side === "mine" ? paired.get(item.id) : [...paired].find(([, v]) => v === item.id)?.[0];
      svg.querySelectorAll("[data-nodes]").forEach((n) => n.classList.toggle("is-hot", on && n.dataset.nodes.split(" ").includes(item.id)));
      svg.querySelectorAll("[data-id]").forEach((n) => n.classList.toggle("is-hot", on && (n.dataset.id === item.id || n.dataset.id === partner)));
    };
    g.addEventListener("mouseenter", () => light(true));
    g.addEventListener("mouseleave", () => light(false));
    g.addEventListener("focus", () => light(true));
    g.addEventListener("blur", () => light(false));
    svg.append(g);
  });
  column(mine, leftX, "start", "mine");
  column(theirs, rightX, "end", "theirs");
  const head = (x, anchor, text) => { const tn = svgEl("text", {x, y: 16, class: "corr__head", "text-anchor": anchor}); tn.textContent = text; svg.append(tn); };
  head(leftX, "start", "yours"); head(rightX, "end", "theirs");
  return svg;
}

// ---- the heat matrix: thoughts × people ------------------------------------------------

export function heatmap({thoughts, people, cell}, {onSelect = null, selected = null} = {}) {
  const table = document.createElement("table");
  table.className = "heat";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  hr.append(document.createElement("th"));
  for (const th of thoughts) { const c = document.createElement("th"); c.className = "heat__col"; c.textContent = th.label.length > 28 ? th.label.slice(0, 27) + "…" : th.label; c.title = th.label; c.scope = "col"; hr.append(c); }
  thead.append(hr); table.append(thead);
  const tbody = document.createElement("tbody");
  for (const p of people) {
    const tr = document.createElement("tr");
    if (p.id === selected) tr.classList.add("is-selected");
    const name = document.createElement("th"); name.textContent = p.name; name.scope = "row"; tr.append(name);
    for (const th of thoughts) {
      const value = cell(p, th);
      const td = document.createElement("td");
      if (value === null || value === undefined) { td.className = "heat__none"; td.textContent = "·"; }
      else {
        // A near miss is drawn faint whatever its number: the engine did not
        // call it a resonance, and a dark cell would say otherwise.
        td.className = value.near ? "heat__cell heat__cell--near" : "heat__cell";
        td.style.setProperty("--heat", String(value.near ? 0 : Math.max(0, Math.min(1, value.strength))));
        td.textContent = value.near ? "·" : value.strength.toFixed(2);
        td.title = `${p.name} × ${th.label}: ${value.strength.toFixed(2)} · ${value.kind}`;
        td.dataset.kind = value.kind;
      }
      if (onSelect) td.addEventListener("click", () => onSelect(p.id));
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  return table;
}

// ---- radar: several people over the same axes ---------------------------------------
//
// The chart a football scout reads: one polygon per person over a fixed set
// of axes, drawn on top of each other, so the shape says at a glance who is
// strong where and where two people cover different parts of the same
// thing. Two uses here: the engine's own dimensions (structure, meaning,
// direct links, systematicity, coverage, absence of contradiction, same
// direction) and, for one thought, your ideas themselves: how much of each
// idea a person's thought answers.

export function hueOf(name) {
  let hash = 0;
  for (const ch of String(name || "")) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return hash % 360;
}

export function radar({axes, series, rings = [0.25, 0.5, 0.75, 1]}, {selected = null, onSelect = null, width = 640, height = 480, labelChars = 18} = {}) {
  const n = Math.max(3, axes.length);
  const cx = width / 2, cy = height / 2;
  // Room for a two-line label outside the rim on every side.
  const R = Math.min(width, height) / 2 - 78;
  const angle = (i) => -Math.PI / 2 + (i / n) * Math.PI * 2;
  const point = (i, v) => [cx + Math.cos(angle(i)) * R * v, cy + Math.sin(angle(i)) * R * v];
  const svg = svgEl("svg", {class: "radar", viewBox: `0 0 ${width} ${height}`, role: "img"});
  const title = svgEl("title"); title.textContent = "How each person measures on every axis";
  svg.append(title);
  // grid
  for (const r of rings) {
    const d = axes.map((_, i) => point(i, r)).map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ") + " Z";
    svg.append(svgEl("path", {d, class: `radar__ring ${r === 1 ? "radar__ring--outer" : ""}`}));
    if (r < 1) { const tn = svgEl("text", {x: cx + 4, y: cy - R * r - 3, class: "radar__tick"}); tn.textContent = r.toFixed(2); svg.append(tn); }
  }
  axes.forEach((axis, i) => {
    const [x, y] = point(i, 1);
    svg.append(svgEl("line", {x1: cx, y1: cy, x2: x, y2: y, class: "radar__spoke"}));
    const [lx, ly] = point(i, 1 + 22 / R);
    const cos = Math.cos(angle(i));
    const anchor = cos > 0.2 ? "start" : cos < -0.2 ? "end" : "middle";
    const label = svgEl("text", {x: lx, y: ly + 4, class: "radar__axis", "text-anchor": anchor});
    const words = String(axis.label || "");
    if (words.length > labelChars) {
      // two lines, broken at a space where possible
      const cut = words.lastIndexOf(" ", labelChars) > 6 ? words.lastIndexOf(" ", labelChars) : labelChars;
      const first = svgEl("tspan", {x: lx, dy: "-0.55em"}); first.textContent = words.slice(0, cut);
      const rest = words.slice(cut).trim();
      const second = svgEl("tspan", {x: lx, dy: "1.1em"}); second.textContent = rest.length > labelChars ? rest.slice(0, labelChars - 1) + "…" : rest;
      label.append(first, second);
    } else label.textContent = words;
    const hint = svgEl("title"); hint.textContent = axis.hint || axis.label;
    label.append(hint);
    svg.append(label);
  });
  // series, the selected one drawn last so it sits on top
  const ordered = [...series].sort((a, b) => (a.id === selected) - (b.id === selected));
  for (const s of ordered) {
    const pts = axes.map((_, i) => point(i, Math.max(0, Math.min(1, Number(s.values[i]) || 0))));
    const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ") + " Z";
    const g = svgEl("g", {class: `radar__series ${s.id === selected ? "is-selected" : ""} ${selected && s.id !== selected ? "is-dim" : ""}`, tabindex: onSelect ? "0" : "-1", role: onSelect ? "button" : "img"});
    g.style.setProperty("--hue", String(s.hue ?? hueOf(s.name)));
    g.dataset.id = s.id;
    g.append(svgEl("path", {d, class: "radar__poly"}));
    pts.forEach(([x, y], i) => {
      const dot = svgEl("circle", {cx: x, cy: y, r: 3.5, class: "radar__dot"});
      const hint = svgEl("title"); hint.textContent = `${s.name} · ${axes[i].label}: ${(Number(s.values[i]) || 0).toFixed(2)}`;
      dot.append(hint);
      g.append(dot);
    });
    const hint = svgEl("title"); hint.textContent = s.name;
    g.append(hint);
    if (onSelect) {
      g.addEventListener("click", () => onSelect(s.id));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(s.id); } });
    }
    svg.append(g);
  }
  return svg;
}
