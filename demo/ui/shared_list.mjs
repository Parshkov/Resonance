/**
 * Everything this person has here, and what state each thing is in.
 *
 * The page showed the one discoverable thought and nothing else. A person
 * could not see what they had shared over time, what was still private, or
 * what they had taken back -- and "am I sharing anything?" is the first
 * question this page owes them an answer to. Worse, the two halves of the
 * product disagreed: a chat reported a withdrawn thought as "kept private
 * here" while the page, correctly, showed nothing.
 *
 * So this reads one list from the server, /api/product/mine, where each
 * thought is sorted into the same three states the chat's whoami uses --
 * discoverable, private, withdrawn -- by the same function. Nothing is
 * decided here; this only says it. It renders at the foot of the thought
 * panel, after the one thought the page already shows, and is absent when
 * there is nothing: an empty list is not an answer, and the line at the top
 * of the panel already says that nothing is discoverable.
 *
 * Three different facts, three different sentences. A private thought was
 * prepared and never made discoverable. A withdrawn thought was discoverable
 * and is not any more. Neither is "shared".
 *
 * Identifiers never reach the screen. The one the server sends is kept in a
 * closure for the stop-sharing call, and that is the only place it goes.
 * Presentation is in /shared_list.css (CSP `default-src 'self'`: an inline
 * style block or a style attribute here would silently do nothing).
 */

import { apiFetch } from "/session.mjs";

const HOST_ID = "shared-list";
const PANEL_ID = "thought-panel";

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// A moment, said the way a person would say it. "Today at 14:02" and "on 3
// September 2026" are things people say; an ISO timestamp is not. The exact
// instant is still on the element, for anyone who hovers or uses a reader.
function whenText(iso) {
  const then = Date.parse(iso || "");
  if (!Number.isFinite(then)) return "";
  const date = new Date(then);
  const now = new Date();
  const dayOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((dayOf(now) - dayOf(date)) / 86400000);
  const time = date.toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit"});
  if (days <= 0) return `today at ${time}`;
  if (days === 1) return `yesterday at ${time}`;
  if (days < 7) return `${days} days ago`;
  return `on ${date.toLocaleDateString(undefined, {day: "numeric", month: "long", year: "numeric"})}`;
}

function moment(iso) {
  const text = whenText(iso);
  if (!text) return null;
  const node = el("time", {textContent: text, dateTime: iso});
  node.title = new Date(Date.parse(iso)).toLocaleString();
  return node;
}

// What each state means, in one sentence, with the moment that matters for
// it. The word at the front is the same word the chat uses.
function stateLine(thought) {
  const light = el("span", {className: "mine-light"});
  light.setAttribute("aria-hidden", "true");
  const word = {discoverable: "Discoverable", private: "Private", withdrawn: "Withdrawn"}[thought.state]
    || "Here";
  return el("p", {className: "mine-state"}, [light, word]);
}

function whatItMeans(thought) {
  const parts = [];
  if (thought.state === "discoverable") {
    const when = moment(thought.shared_at || thought.prepared_at);
    parts.push("Shared", when ? " " : "", when, ". ");
    parts.push("People whose reasoning has the same shape can find it, and it keeps looking for them.");
  } else if (thought.state === "withdrawn") {
    const when = moment(thought.withdrawn_at);
    parts.push("Withdrawn", when ? " " : "", when, ". ");
    parts.push("It is not discoverable any more, and it is not reported to anyone as a match.");
    const shared = moment(thought.shared_at);
    if (shared) parts.push(" It had been shared ", shared, ".");
  } else {
    const when = moment(thought.prepared_at);
    parts.push("Prepared", when ? " " : "", when, " and kept here. ");
    parts.push("It was never made discoverable, so nobody can find it.");
  }
  return el("p", {className: "mine-meaning"}, parts);
}

// The structure the thought carries: the links between ideas, then any idea
// that is in no link. This is the whole of what a thought is here -- the
// words a person wrote are never kept, only this.
function structure(thought) {
  const nodes = thought.nodes || [];
  const relations = thought.relations || [];
  const summary = el("summary", {className: "mine-count",
    textContent: `${plural(nodes.length, "idea", "ideas")} · ${plural(relations.length, "link", "links")} between them`});
  const details = el("details", {className: "mine-structure"}, [summary]);
  const links = el("ol", {className: "mine-links"});
  links.setAttribute("aria-label", "Links between the ideas");
  const linked = new Set();
  for (const relation of relations) {
    linked.add(relation.from); linked.add(relation.to);
    links.append(el("li", {className: "mine-link"}, [
      el("span", {className: "mine-node", textContent: relation.from}),
      el("span", {className: "mine-rel", textContent: relation.type}),
      el("span", {className: "mine-node", textContent: relation.to}),
    ]));
  }
  if (relations.length) details.append(links);
  const loose = nodes.filter((n) => !linked.has(n.label));
  if (loose.length) {
    details.append(el("p", {className: "mine-loose"}, [
      relations.length ? "Also: " : "",
      ...loose.flatMap((n, i) => [i ? ", " : "", el("span", {className: "mine-node", textContent: n.label})]),
    ]));
  }
  // The page above already draws what is discoverable, so those stay folded
  // and the count is enough. A private or withdrawn thought is shown nowhere
  // else, so its structure is open: this is the only place to see it.
  details.open = thought.state !== "discoverable";
  return details;
}

// Stopping is a real decision: it asks once, here, and says exactly what will
// happen -- never a browser dialog, which cannot say anything in the page's
// own words and is dismissed before it is read.
function stopControl(thought, host, item, discoverableCount) {
  const stop = el("button", {type: "button", className: "collab-button", textContent: "Stop sharing"});
  stop.addEventListener("click", () => {
    const box = el("div", {className: "mine-stop", role: "group"});
    box.setAttribute("aria-label", "Confirm stop sharing this thought");
    const yes = el("button", {type: "button", className: "collab-button collab-button--primary", textContent: "Yes, stop"});
    const keep = el("button", {type: "button", className: "collab-button collab-button--quiet", textContent: "Keep sharing"});
    const status = el("p", {className: "mine-error"});
    keep.addEventListener("click", () => { box.replaceWith(stop); stop.focus(); });
    yes.addEventListener("click", async () => {
      yes.disabled = true; keep.disabled = true;
      try {
        // The only use of the identifier: naming which thought to the server.
        await apiFetch("POST", "/api/product/revoke", {session_id: thought.session_id, confirmed: true});
        // Say it the moment it is true, in the same words the re-read will
        // use; the re-read then replaces this with the server's own record.
        item.dataset.state = "withdrawn";
        item.querySelector(".mine-state")?.replaceChildren(el("span", {className: "mine-light"}), "Withdrawn");
        item.querySelector(".mine-meaning")?.replaceChildren(
          "Withdrawn just now. It is not discoverable any more, and it is not reported to anyone as a match.");
        box.remove();
        scheduleLoad();
        // The panel above draws one discoverable thought, and re-reads it on
        // its own only when sharing flips off altogether. Withdraw one of two
        // and it kept drawing the withdrawn one under "What others can see",
        // which is the one thing this page must never say. Asking it to
        // re-read is the only hook it offers; the flip case it handles itself.
        if (discoverableCount > 1) document.dispatchEvent(new CustomEvent("resonance:discovered"));
      } catch (error) {
        yes.disabled = false; keep.disabled = false;
        status.textContent = `It is still shared: ${error.message}`;
      }
    });
    box.append(
      el("p", {textContent: "This thought leaves discovery now and stops looking. Anyone it matched stops seeing it. It stays in this list as withdrawn."}),
      yes, keep, status);
    stop.replaceWith(box);
    yes.focus();
  });
  host.append(stop);
}

function renderItem(thought, discoverableCount) {
  const item = el("li", {className: "mine-item"});
  item.dataset.state = thought.state;
  const title = (thought.topic || thought.nodes?.[0]?.label || "A thought").trim();
  const head = el("div", {className: "mine-head"}, [
    stateLine(thought),
    el("h4", {className: "mine-title", textContent: title}),
    whatItMeans(thought),
  ]);
  const actions = el("div", {className: "mine-actions"});
  if (thought.state === "discoverable") stopControl(thought, actions, item, discoverableCount);
  item.append(head, structure(thought), actions);
  return item;
}

function host() {
  let node = document.getElementById(HOST_ID);
  if (node) return node;
  const panel = document.getElementById(PANEL_ID);
  if (!panel) return null;                       // not this page
  node = el("section", {className: "mine", id: HOST_ID});
  node.setAttribute("aria-labelledby", "mine-heading");
  node.hidden = true;
  panel.append(node);
  return node;
}

function render(payload) {
  const node = host();
  if (!node) return;
  const thoughts = payload?.thoughts || [];
  if (!thoughts.length) {
    // Nothing here: nothing to list, and the line at the top of the panel
    // already says so. A heading over an empty list would be a second answer.
    node.replaceChildren();
    node.hidden = true;
    return;
  }
  const list = el("ol", {className: "mine-list"});
  const discoverable = thoughts.filter((t) => t.state === "discoverable").length;
  for (const thought of thoughts) list.append(renderItem(thought, discoverable));
  node.replaceChildren(
    el("h3", {className: "eyebrow mine-heading", id: "mine-heading", textContent: "Everything you have here"}),
    el("p", {className: "mine-lede", textContent:
      "Each thought is one of three things: discoverable, private, or withdrawn. "
      + "Your words are not kept anywhere; only the ideas and the links between them are."}),
    list);
  node.hidden = false;
}

function hide() {
  const node = document.getElementById(HOST_ID);
  if (node) { node.replaceChildren(); node.hidden = true; }
}

let loadTimer = null;
let retryTimer = null;

// The server meters reads of a person's own record, and a page load spends
// that budget on several readers at once. When this read is refused, it is
// usually only that; one more try after the meter has moved on is enough,
// and until then the list is simply not on the page rather than wrong.
const RETRY_AFTER_MS = 6000;

async function load(attempt = 0) {
  if (!document.getElementById(PANEL_ID)) return;
  clearTimeout(retryTimer);
  try {
    // A plain read, on purpose: apiFetch would create a guest account for a
    // visitor who has none, and someone who has not arrived yet has nothing
    // here to list.
    const response = await fetch("/api/product/mine", {credentials: "same-origin", cache: "no-store"});
    if (response.ok) {
      render(await response.json());
      return;
    }
    hide();
    // 401 is an answer (nobody is signed in here); anything else may be the meter.
    if (response.status !== 401 && attempt === 0) {
      retryTimer = setTimeout(() => { load(1); }, RETRY_AFTER_MS);
    }
  } catch {
    hide();
  }
}

// Writes come in bursts (prepare, then share; a withdrawal here, then the
// panel above re-reading): one read for all of them.
function scheduleLoad() {
  clearTimeout(loadTimer);
  loadTimer = setTimeout(() => { load(0); }, 150);
}

function init() {
  if (!document.getElementById(PANEL_ID)) return;
  load(0);
  document.addEventListener("resonance:write", (event) => {
    // Marking news as seen changes nothing in this list.
    if (event.detail?.path === "/api/product/resonances/seen") return;
    scheduleLoad();
  });
  // Signed out where a sign-in exists: there is no account to list for.
  document.addEventListener("resonance:sign-in-required", hide);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

export { init, load, whenText };
