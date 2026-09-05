/**
 * Where the people in your result are, on the earth.
 *
 * The resonance map beside this one places people by how closely their
 * reasoning matches yours; distance there means structure, not geography.
 * This is the other question a person asks about a stranger who thinks the
 * way they do -- where are they? -- and until now the only answer was a
 * drawing sent into a chat by the MCP bridge. Someone on the site had no way
 * to see it.
 *
 * Three rules, all of them the product's and none of them decided here:
 *
 *   - A place appears only where that person chose to share a rough one, and
 *     the server already rounded it to a tenth of a degree. Nothing about
 *     where anyone is ever touched who matched or in what order; the page
 *     says so, in words, under the map.
 *   - A person who shared no place is still named, as someone who chose not
 *     to say. That is a different fact from "nobody is here", and the two
 *     must never look the same.
 *   - Region counts come from the server's k-anonymous buckets. A region with
 *     fewer people than the minimum is not counted here either; the page only
 *     says how many such regions there were.
 *
 * Nothing external: the continents are a hand-drawn sketch below, coarse
 * enough to place a city and no more, and the page is served under
 * default-src 'self' where a map tile could not load anyway.
 *
 * Reads `/api/geo`, the same authorized result app.mjs draws, reduced to what
 * a map needs. It listens for the same page events app.mjs re-reads on, so
 * the two maps never describe different results.
 */

const GEO_CONTRACT = "resonance-geo-view/0.1";
const SHARE_REQUIRED = "share_required";
const SVG_NS = "http://www.w3.org/2000/svg";

// Plate carrée at one scale in both directions, so the sketch keeps its
// proportions. Everything above 84° and below 60° south is ice and empty
// water; leaving it out gives the inhabited world the room instead.
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

// ---- the sketch ----------------------------------------------------------
//
// Outlines as [longitude, latitude] corners. They are drawn from memory of
// the atlas, not traced from one, and are deliberately blunt: a location on
// this map is a city rounded to ten kilometres, and a coastline finer than
// that would promise a precision the data does not have. Inland seas are
// drawn over the land in the water colour rather than carved out of it.
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

// ---- what the page says ----------------------------------------------------
//
// Every sentence is built here, from the payload alone, so the words can be
// checked without a browser. Nothing is computed about people: names, places
// and counts are the server's; only the grammar is the page's.

function assertGeoView(payload) {
  if (payload?.contract_version !== GEO_CONTRACT) {
    throw new Error("Unsupported geographic view contract");
  }
  if (!Array.isArray(payload.people)) {
    throw new Error("Geographic view is incomplete");
  }
}

export function placeLabel(place) {
  if (!place) return "";
  const city = String(place.city || "").trim();
  const region = String(place.region || "").trim();
  if (city && region && city !== region) return `${city}, ${region}`;
  return city || region;
}

export function distanceWords(km) {
  if (!Number.isFinite(km)) return "";
  if (km < 50) return "within about 50 km of you";
  return `about ${Math.round(km).toLocaleString("en-US")} km from you`;
}

// "A, B and C"; past six names the rest are counted, so a long list of people
// who said nothing about where they are does not crowd out the map of those
// who did.
export function nameList(names, limit = 6) {
  const shown = names.slice(0, limit);
  const rest = names.length - shown.length;
  if (rest > 0) shown.push(`${rest} ${rest === 1 ? "other" : "others"}`);
  if (shown.length <= 1) return shown.join("");
  return `${shown.slice(0, -1).join(", ")} and ${shown[shown.length - 1]}`;
}

export function summarySentence(locatedCount, total) {
  if (total === 0) return "";
  if (locatedCount === total) {
    return total === 1 ? "The one person here shared where they are."
      : `All ${total} people shared where they are.`;
  }
  return `${locatedCount} of ${total} people shared where they are.`;
}

export function unlocatedSentence(names) {
  if (!names.length) return "";
  return `${nameList(names)} chose not to say where they are.`;
}

export function youSentence(you) {
  if (you) return `You: ${placeLabel(you)}.`;
  return "You have not shared where you are, so no distances are shown.";
}

export function regionsSentence(regions) {
  const shown = Array.isArray(regions?.shown) ? regions.shown : [];
  const hidden = Number(regions?.hidden) || 0;
  const minimum = Number(regions?.minimum) || 0;
  const parts = [];
  if (shown.length) {
    parts.push(`Counted by region: ${shown.map((b) => `${b.region} ${b.count}`).join(", ")}.`);
  }
  if (hidden > 0) {
    parts.push(`${hidden === 1 ? "One region" : `${hidden} regions`} with fewer than ${minimum} ` +
      `people ${hidden === 1 ? "is" : "are"} not counted, so nobody can be picked out by where they are.`);
  }
  return parts.join(" ");
}

export const ABSENT_SENTENCE =
  "Nobody who matched has said where they are, so there is no map of them.";

export const NOTE_SENTENCE =
  "Shown only where that person chose to share it, and rounded to about ten kilometres. " +
  "Where anyone is never affects who matches, or in what order.";

// The model the page renders: who has a place, who chose not to say, and how
// people who share one rounded spot are spread so each can still be pointed
// at. Server order throughout; nothing is sorted.
export function geoModel(payload) {
  assertGeoView(payload);
  const located = [];
  const unlocated = [];
  for (const person of payload.people) {
    if (person.place) located.push(person);
    else unlocated.push(person);
  }
  const you = payload.you || null;
  const points = [];
  const spots = new Map();
  const place = (entry) => {
    const key = `${entry.place.lat},${entry.place.lon}`;
    const [x, y] = project(entry.place.lat, entry.place.lon);
    const crowd = spots.get(key) || 0;
    spots.set(key, crowd + 1);
    // Two people rounded to the same tenth of a degree would sit exactly on
    // top of each other; the second and later step out around the first,
    // to the left, above and below first, because the name sits to the right.
    const offset = crowd === 0 ? [0, 0] : SAME_SPOT_STEPS[(crowd - 1) % SAME_SPOT_STEPS.length];
    points.push({...entry, x: Math.round((x + offset[0]) * 10) / 10,
                 y: Math.round((y + offset[1]) * 10) / 10});
  };
  if (you) place({you: true, name: "You", place: you});
  for (const person of located) place(person);
  return {
    located, unlocated, you, points,
    total: payload.people.length,
    regions: payload.regions || {shown: [], hidden: 0, minimum: 0},
  };
}

// The exact strings a person reads, in order, for a given payload. This is
// what the tests check: no identifier, no raw number, every case named.
export function sentences(payload) {
  const model = geoModel(payload);
  if (!model.total) return [];
  if (!model.located.length) return [ABSENT_SENTENCE];
  const lines = [summarySentence(model.located.length, model.total)];
  lines.push(youSentence(model.you));
  for (const person of model.located) lines.push(personLine(person));
  if (model.unlocated.length) lines.push(unlocatedSentence(model.unlocated.map((p) => p.name)));
  const regions = regionsSentence(model.regions);
  if (regions) lines.push(regions);
  lines.push(NOTE_SENTENCE);
  return lines;
}

function personLine(person) {
  const bits = [`${person.name}: ${placeLabel(person.place)}`];
  const distance = distanceWords(person.about_km);
  if (distance) bits.push(distance);
  if (person.example) bits.push("an example from the seeded corpus");
  return bits.join(" · ");
}

// ---- the page --------------------------------------------------------------

function el(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgEl(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function removeExisting() {
  document.getElementById("geo-panel")?.remove();
  document.getElementById("geo-absent")?.remove();
}

function mount() {
  return document.querySelector("#people .people-grid");
}

function focusPerson(sessionId) {
  document.dispatchEvent(new CustomEvent("resonance:focus-session", {detail: {sessionId}}));
}

// The map is drawn in its own 1000x400 coordinates and then scaled to whatever
// width the column happens to be, so a radius written in those coordinates is a
// different number of real pixels on a phone than on a desktop -- which is how
// a target that measures 24px in one place is 12px in another. The hit discs
// are therefore sized from the scale the map is actually drawn at, and resized
// with it. `non-scaling-stroke` would express this in CSS, but Chrome does not
// hit-test the scaled stroke, so the target would be invisible AND unreachable.
const MIN_TARGET = 24;

export function sizeHitAreas(svg, viewBoxWidth = MAP_WIDTH) {
  const apply = () => {
    const width = svg.getBoundingClientRect().width;
    if (!width) return;
    const radius = (MIN_TARGET / 2) * (viewBoxWidth / width);
    for (const hit of svg.querySelectorAll(".geo-hit")) {
      hit.setAttribute("r", radius.toFixed(2));
    }
  };
  apply();
  if (typeof ResizeObserver === "function") new ResizeObserver(apply).observe(svg);
  return svg;
}

function renderMapSvg(model) {
  const svg = svgEl("svg", {
    class: "geo-map", viewBox: `0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`, role: "img",
    "aria-labelledby": "geo-map-title geo-map-desc",
  });
  const title = svgEl("title", {id: "geo-map-title"});
  title.textContent = "Where the people in your result are, for those who chose to share it";
  const desc = svgEl("desc", {id: "geo-map-desc"});
  desc.textContent = "A sketch of the continents with one point per person who shared a rough " +
    "location, rounded to about ten kilometres. The list under the map names each of them, " +
    "and the people who chose not to say.";
  svg.append(title, desc);

  const land = svgEl("g", {class: "geo-land-layer", "aria-hidden": "true"});
  for (const corners of LAND) land.append(svgEl("path", {class: "geo-land", d: outlinePath(corners)}));
  for (const corners of INLAND_WATER) land.append(svgEl("path", {class: "geo-water", d: outlinePath(corners)}));
  svg.append(land);

  // A light graticule every thirty degrees, the equator a shade firmer, so
  // the eye has something to measure the sketch against.
  const grid = svgEl("g", {class: "geo-grid-layer", "aria-hidden": "true"});
  for (let lon = -150; lon <= 150; lon += 30) {
    const [x] = project(0, lon);
    grid.append(svgEl("line", {class: "geo-grid", x1: x, y1: 0, x2: x, y2: MAP_HEIGHT}));
  }
  for (let lat = -30; lat <= 60; lat += 30) {
    const [, y] = project(lat, 0);
    grid.append(svgEl("line", {class: `geo-grid${lat === 0 ? " is-equator" : ""}`,
                               x1: 0, y1: y, x2: MAP_WIDTH, y2: y}));
  }
  svg.append(grid);

  const points = svgEl("g", {class: "geo-point-layer"});
  for (const point of model.points) {
    const kind = point.you ? "is-you" : (point.resonance ? "is-resonance" : "is-other");
    const label = point.you ? "You" : point.name;
    const where = placeLabel(point.place);
    const marker = svgEl("g", {
      class: `geo-point ${kind}${point.example ? " is-example" : ""}`,
      transform: `translate(${point.x} ${point.y})`,
      "aria-label": `${label}, ${where}`,
    });
    const hint = svgEl("title");
    hint.textContent = `${label} · ${where}`;
    // A 6px dot is a 12px target, and a person picking someone off a map is
    // usually doing it with a thumb. The dot stays the size the map needs; an
    // invisible disc behind it carries the target, sized by sizeHitAreas().
    marker.append(hint, svgEl("circle", {class: "geo-hit", r: 12}),
                  svgEl("circle", {class: "geo-dot", r: point.you ? 5 : 6}));
    // Labels sit to the right of the point and flip to the left near the
    // edge, so no name runs off the map.
    const flip = point.x > MAP_WIDTH - 130;
    const text = svgEl("text", {class: "geo-label", x: flip ? -10 : 10, y: 4,
                                "text-anchor": flip ? "end" : "start"});
    text.textContent = label;
    marker.append(text);
    if (!point.you && point.session_id) {
      marker.setAttribute("role", "button");
      marker.setAttribute("tabindex", "0");
      marker.addEventListener("click", () => focusPerson(point.session_id));
      marker.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          focusPerson(point.session_id);
        }
      });
    }
    points.append(marker);
  }
  svg.append(points);
  return svg;
}

function renderKey() {
  const key = el("p", "geo-key");
  const entry = (kind, words) => {
    const item = el("span", "geo-key-item");
    const swatch = el("span", `geo-swatch ${kind}`);
    swatch.setAttribute("aria-hidden", "true");
    item.append(swatch, document.createTextNode(words));
    return item;
  };
  key.append(
    entry("is-you", "you"),
    entry("is-resonance", "the same shape as yours"),
    entry("is-other", "returned, but the engine does not call it a resonance"),
    entry("is-example", "an example from the seeded corpus"),
  );
  return key;
}

export function render(payload) {
  const grid = mount();
  if (!grid) return;
  removeExisting();
  const model = geoModel(payload);
  if (!model.total) return;

  // People, but none who said where they are. A map with nobody on it would
  // say "nobody is anywhere"; the truth is that they chose not to say.
  if (!model.located.length) {
    grid.append(el("p", "geo-absent", ABSENT_SENTENCE)).id = "geo-absent";
    return;
  }

  const panel = el("section", "panel geo-panel");
  panel.id = "geo-panel";
  panel.setAttribute("aria-labelledby", "geo-heading");

  const head = el("div", "panel-head");
  const heading = el("h3", "", "Where they are");
  heading.id = "geo-heading";
  head.append(heading, el("span", "geo-count", summarySentence(model.located.length, model.total)));
  panel.append(head);

  const frame = el("div", "geo-frame");
  const map = renderMapSvg(model);
  frame.append(map);
  // After it is in the document: a detached node has no width to scale from.
  requestAnimationFrame(() => sizeHitAreas(map));
  panel.append(frame, renderKey());

  const list = el("ol", "geo-list");
  list.setAttribute("aria-label", "Each person and where they are, in the engine's order");
  if (model.you) list.append(el("li", "geo-row is-you", youSentence(model.you)));
  for (const person of model.located) {
    const row = el("li", `geo-row${person.resonance ? " is-resonance" : " is-other"}`);
    const name = el("button", "geo-name", person.name);
    name.type = "button";
    name.addEventListener("click", () => focusPerson(person.session_id));
    row.append(name, el("span", "geo-place", placeLabel(person.place)));
    const distance = distanceWords(person.about_km);
    if (distance) row.append(el("span", "geo-distance", distance));
    if (person.example) row.append(el("span", "geo-example", "example from the seeded corpus"));
    list.append(row);
  }
  panel.append(list);

  if (!model.you) panel.append(el("p", "geo-you", youSentence(null)));
  if (model.unlocated.length) {
    panel.append(el("p", "geo-unlocated", unlocatedSentence(model.unlocated.map((p) => p.name))));
  }
  const regions = regionsSentence(model.regions);
  if (regions) panel.append(el("p", "geo-regions", regions));
  panel.append(el("p", "geo-note", NOTE_SENTENCE));
  grid.append(panel);
}

// ---- reading -----------------------------------------------------------------

async function load() {
  let payload;
  try {
    const response = await fetch("/api/geo", {cache: "no-store"});
    payload = await response.json();
    // Nothing shared, or a cookie this server no longer knows: nothing of
    // theirs was searched for, so there is nobody to place. Same answer
    // app.mjs takes from /api/discover.
    if ((response.status === 409 && payload?.error === SHARE_REQUIRED) || response.status === 401) {
      removeExisting();
      return;
    }
    if (!response.ok) throw new Error(payload?.message || payload?.error || `HTTP ${response.status}`);
    render(payload);
  } catch (error) {
    // The resonance map has already told the person what could not be read;
    // a second notice for the same result would only repeat it. Show nothing
    // rather than a map of a result that was not read.
    removeExisting();
  }
}

// The same moments app.mjs re-reads the result: a discovery run by an agent
// through the page's tools, and consent actually flipping. Costs one read per
// load, and no read on the writes that do not change who is in the result.
let lastShared = null;
function onConsentState(shared) {
  if (lastShared === null) {
    lastShared = shared;
    return;
  }
  if (shared === lastShared) return;
  lastShared = shared;
  load();
}

function boot() {
  document.addEventListener("resonance:discovered", () => { load(); });
  document.addEventListener("resonance:consent", (event) => {
    onConsentState(event.detail?.shared === true);
  });
  load();
}

if (typeof document !== "undefined") boot();
