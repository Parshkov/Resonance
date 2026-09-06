/**
 * The page: a router, a header, and one view per screen.
 *
 *   /            what is new, who resonates, your thoughts and groups at a glance
 *   /thoughts    the thoughts you have here: share, edit, share again, withdraw, delete
 *   /people      who resonates with you, drawn as a constellation, a map and a matrix; why
 *   /talk        introductions and conversations
 *   /groups      groups around one idea; /groups/<id> is one of them
 *   /connect     the same product from the chat you already use
 *
 * Every view is a pure function of the store and a little screen-local
 * state. Nothing here matches, ranks or rescores: every number shown is one
 * the engine returned, and every order is the engine's order.
 */

import * as store from "/store.mjs";
import { t } from "/strings.mjs";
import { constellation, correspondence, heatmap, worldMap } from "/maps.mjs";

// ---- tiny DOM helpers --------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key in node && key !== "style") node[key] = value;
    else node.setAttribute(key, value);
  }
  // Children may be nested arrays (a conditional group of nodes).
  for (const child of [].concat(children).flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function link(href, label, props = {}) {
  return el("a", {href, dataset: {link: "1"}, ...props}, label);
}

function button(label, onclick, {variant = "", type = "button", disabled = false, title = null} = {}) {
  return el("button", {type, class: `btn ${variant}`.trim(), onclick, disabled, title}, label);
}

function timeAgo(iso) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return "";
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return t("time.now");
  if (minutes < 60) return t("time.minutes", {n: minutes});
  const hours = Math.round(minutes / 60);
  if (hours < 48) return t("time.hours", {n: hours});
  return t("time.days", {n: Math.round(hours / 24)});
}

function score(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "—";
}

function verdict(classification) {
  const key = `verdict.${String(classification || "").toLowerCase()}`;
  const said = t(key);
  return said === key ? String(classification || "") : said;
}

function strengthWord(structural) {
  const value = Number(structural) || 0;
  if (value >= 0.85) return t("people.strength.very_close");
  if (value >= 0.6) return t("people.strength.close");
  if (value >= 0.35) return t("people.strength.partial");
  return t("people.strength.faint");
}

function relationWord(type) {
  return String(type || "").replace(/_/g, " ");
}

// A person's mark: two letters on a colour that is theirs alone.
function avatar(name, size = "") {
  const words = String(name || "?").split(/\s+/).filter(Boolean);
  const initials = (words[0]?.[0] || "?") + (words[1]?.[0] || "");
  let hash = 0;
  for (const ch of String(name || "")) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const node = el("span", {class: `avatar ${size}`.trim(), "aria-hidden": "true"}, initials.toUpperCase());
  node.style.setProperty("--hue", String(hash % 360));
  return node;
}

// A thought's structure, the one way it is drawn everywhere: ideas as chips,
// then each link as a sentence.
function structure(nodes = [], relations = []) {
  const labels = new Map();
  for (const node of nodes) labels.set(node.id ?? node.label, node.label);
  const box = el("div", {class: "structure"});
  box.append(el("ul", {class: "ideas"}, nodes.map((node) => el("li", {class: "idea"}, node.label))));
  box.append(el("ul", {class: "links"}, relations.map((rel) => {
    const from = rel.from ?? labels.get(rel.source) ?? rel.source;
    const to = rel.to ?? labels.get(rel.target) ?? rel.target;
    return el("li", {class: "link-row"}, [el("span", {}, from), el("span", {class: "link-type"}, relationWord(rel.type)), el("span", {}, to)]);
  })));
  return box;
}

// The profile of one match on three axes the engine reports: structure,
// meaning, coverage. Bars, so many people can be compared at a glance.
function profile(scores = {}) {
  const rows = [["structural", "structure"], ["semantic", "meaning"], ["coverage_containment", "coverage"]];
  return el("div", {class: "profile"}, rows.map(([key, label]) => {
    const value = Math.max(0, Math.min(1, Number(scores[key]) || 0));
    const bar = el("div", {class: "profile__bar"}, el("div", {class: "profile__fill"}));
    bar.lastChild.style.width = `${Math.round(value * 100)}%`;
    return el("div", {class: "profile__row"}, [el("span", {class: "profile__label"}, label), bar, el("span", {class: "profile__value"}, score(value))]);
  }));
}

function notice(message) { document.dispatchEvent(new CustomEvent("resonance:notice", {detail: {message}})); }
function toast(message) { document.dispatchEvent(new CustomEvent("resonance:toast", {detail: {message}})); }

async function attempt(action) {
  try { return await action(); } catch (error) { notice(t("error.generic", {message: error.message})); return null; }
}

function stateDot(stateWord) {
  return el("span", {class: `dot dot--${stateWord}`, title: t(`thoughts.state.${stateWord}`)});
}

function empty(title, body, action = null) {
  return el("div", {class: "empty"}, [el("p", {class: "empty__title"}, title), body ? el("p", {class: "empty__body"}, body) : null, action]);
}

// Which menu is open and which structures are unfolded live in screen state,
// not in the DOM: a poll can redraw the screen at any moment, and what the
// person opened must still be open afterwards.
function menu(id, items) {
  const open = ui.menuOpen === id;
  const wrap = el("div", {class: "kebab"});
  const trigger = el("button", {type: "button", class: "kebab__button", "aria-label": t("more"), "aria-haspopup": "true", "aria-expanded": String(open)}, "···");
  const panel = el("div", {class: "kebab__panel", hidden: !open}, items.filter(Boolean).map(([label, action, danger]) =>
    el("button", {type: "button", class: `kebab__item ${danger ? "is-danger" : ""}`, onclick: () => { ui.menuOpen = null; action(); }}, label)));
  trigger.addEventListener("click", (e) => { e.stopPropagation(); ui.menuOpen = open ? null : id; render(); });
  wrap.append(trigger, panel);
  return wrap;
}
document.addEventListener("click", (event) => {
  if (ui.menuOpen && !event.target.closest(".kebab")) { ui.menuOpen = null; render(); }
});

function disclosure(id, summary, body) {
  const node = el("details", {class: "disclosure", open: ui.unfolded.has(id)}, [el("summary", {}, summary), body]);
  node.addEventListener("toggle", () => { if (node.open) ui.unfolded.add(id); else ui.unfolded.delete(id); });
  return node;
}

// ---- router ----------------------------------------------------------------------------

const ROUTES = [
  {path: /^\/$/, view: homeView, nav: "home"},
  {path: /^\/thoughts$/, view: thoughtsView, nav: "thoughts"},
  {path: /^\/people$/, view: peopleView, nav: "people"},
  {path: /^\/talk(?:\/([^/]+))?$/, view: talkView, nav: "talk"},
  {path: /^\/groups$/, view: groupsView, nav: "groups"},
  {path: /^\/groups\/([^/]+)$/, view: groupView, nav: "groups"},
  {path: /^\/connect$/, view: connectView, nav: "connect"},
];

function current() {
  const url = new URL(window.location.href);
  for (const route of ROUTES) {
    const match = url.pathname.match(route.path);
    if (match) return {...route, param: match[1] || null, query: url.searchParams};
  }
  return {...ROUTES[0], param: null, query: url.searchParams};
}

export function navigate(path, {replace = false} = {}) {
  if (replace) history.replaceState({}, "", path); else history.pushState({}, "", path);
  ui.drawer = null;
  render();
  window.scrollTo(0, 0);
}

document.addEventListener("click", (event) => {
  const anchor = event.target.closest("a[data-link]");
  if (!anchor || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
  const url = new URL(anchor.href, window.location.href);
  if (url.origin !== window.location.origin) return;
  event.preventDefault();
  navigate(url.pathname + url.search);
});
window.addEventListener("popstate", () => render());

// ---- screen-local state -------------------------------------------------------------

const ui = {
  composer: null,            // {step, text, preview, busy, place}
  editing: null,             // {session_id, title, domain, nodes, relations, state, busy}
  stopAsk: null,
  deleteAsk: null,
  thoughtsFilter: "all",
  peopleFilter: "all",       // "all" | session_id
  peopleView: "constellation", // constellation | where | matrix
  peopleSelected: null,
  drawer: null,              // {kind: "person", id} | null
  askOpen: null,
  askSent: new Set(),
  talkThread: null,
  groupTab: "discussion",
  newGroup: null,
  contribute: null,
  connectTab: "claude",
  drafts: {},
  menuOpen: null,
  unfolded: new Set(),
};

function draftField(tag, id, props = {}) {
  const node = el(tag, {...props, id, value: ui.drafts[id] || ""});
  node.addEventListener("input", () => { ui.drafts[id] = node.value; });
  return node;
}
function clearDraft(id) { delete ui.drafts[id]; }

// ---- header -------------------------------------------------------------------------------

function counts() {
  const unseen = store.alerts().filter((a) => !a.seen_at).length;
  const requests = store.intros().incoming.filter((r) => r.state === "requested").length;
  const {topics, invitations} = store.topics();
  const groupsNew = invitations.length + topics.reduce((sum, g) => sum + (Number(g.new_for_you) || 0), 0);
  return {home: unseen + requests + invitations.length, people: unseen, talk: requests, groups: groupsNew};
}

function renderHeader() {
  const nav = document.getElementById("page-nav");
  const route = current();
  const badge = counts();
  const signedOut = store.getState().phase === "signed-out";
  const items = signedOut ? [["connect", "/connect"]]
    : [["home", "/"], ["thoughts", "/thoughts"], ["people", "/people"], ["talk", "/talk"], ["groups", "/groups"], ["connect", "/connect"]];
  nav.replaceChildren(...items.map(([key, href]) => {
    const a = link(href, [t(`nav.${key}`), badge[key] ? el("span", {class: "nav-badge", "aria-label": t("nav.new")}, String(badge[key])) : null], {class: "nav-link"});
    if (route.nav === key) a.setAttribute("aria-current", "page");
    return a;
  }));
  renderAccount();
}

function signInHref() {
  const base = store.getState().overview?.sign_in_url || "/auth/sign-in";
  return `${base}?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
}

function renderAccount() {
  const slot = document.getElementById("account-slot");
  const s = store.getState();
  const account = store.account();
  slot.replaceChildren();
  if (s.phase === "signed-out" || !account?.display_label) {
    slot.append(el("a", {class: "btn btn--primary btn--small", href: signInHref()}, t("account.signin")), settingsMenu(null));
    return;
  }
  slot.append(settingsMenu(account));
}

function settingsMenu(account) {
  const wrap = el("div", {class: "menu"});
  const label = account ? account.display_label : "Aa";
  const trigger = el("button", {type: "button", class: "menu__button", "aria-haspopup": "true", "aria-expanded": "false", "aria-label": t("account.menu")},
    account ? [avatar(label), el("span", {class: "menu__name"}, label)] : [el("span", {class: "avatar avatar--quiet"}, "Aa")]);
  const panel = el("div", {class: "menu__panel", hidden: true});
  if (account) {
    panel.append(el("p", {class: "menu__caption"}, t("account.seen_as")), el("p", {class: "menu__value"}, label), el("p", {class: "menu__note"}, t("account.pseudonym_note")));
    if (account.signed_in && account.sign_in_email) {
      panel.append(el("p", {class: "menu__caption"}, t("account.signed_in_as")), el("p", {class: "menu__value"}, account.sign_in_email), el("p", {class: "menu__note"}, t("account.only_you")));
    } else if (account.signed_in === false) {
      panel.append(el("p", {class: "menu__note"}, t("account.browser_only")));
    }
  }
  const theme = window.__resonanceTheme;
  const choice = theme?.choice?.() || document.documentElement.getAttribute("data-theme-choice") || "light";
  panel.append(el("div", {class: "menu__row"}, [el("span", {class: "menu__caption"}, t("account.colours")),
    el("div", {class: "segmented", role: "radiogroup"}, ["light", "dark", "system"].map((value) =>
      el("label", {class: "segmented__option"}, [
        el("input", {type: "radio", name: "theme", value, checked: value === choice,
          onchange: () => { if (theme?.choose) theme.choose(value); else document.documentElement.setAttribute("data-theme", value === "dark" ? "dark" : "light"); }}),
        el("span", {}, t(`account.theme.${value}`))])))]));
  if (account && account.signed_in) {
    const form = el("form", {method: "post", action: "/auth/sign-out", class: "menu__out"});
    form.append(el("button", {type: "submit", class: "btn btn--small"}, t("account.signout")));
    panel.append(form);
  }
  trigger.addEventListener("click", (e) => { e.stopPropagation(); const open = panel.hidden; panel.hidden = !open; trigger.setAttribute("aria-expanded", String(open)); });
  document.addEventListener("click", (event) => { if (!wrap.contains(event.target)) { panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); } });
  wrap.append(trigger, panel);
  return wrap;
}

// ---- home ------------------------------------------------------------------------------------

function homeView() {
  const s = store.getState();
  const frag = document.createDocumentFragment();
  if (s.phase === "signed-out") { frag.append(landing(true)); return frag; }
  const mine = store.thoughts();
  if (!mine.length) { frag.append(landing(false)); return frag; }
  const account = store.account();
  const discoverable = mine.filter((r) => r.state === "discoverable").length;
  const peopleFound = foundPeople().people.length;
  const groups = store.topics().topics.length;
  frag.append(el("header", {class: "dash-head"}, [
    el("div", {}, [el("h1", {}, t("home.greeting", {who: account?.display_label || ""})),
      el("p", {class: "lede"}, [discoverable ? t("home.status.thoughts", {n: discoverable}) : t("home.status.none"), " · ", t("home.status.people", {n: peopleFound}), " · ", t("home.status.groups", {n: groups})])]),
    el("div", {class: "row"}, [link("/thoughts?new=1", t("home.cta.share"), {class: "btn btn--primary"})]),
  ]));
  frag.append(newsSection());
  const grid = el("div", {class: "dash-grid"});
  grid.append(homePeople(), homeThoughts(), homeGroups(), homeTalks());
  frag.append(grid);
  return frag;
}

function landing(signedOut) {
  const hero = el("section", {class: "hero"}, [
    el("h1", {class: "hero__title"}, t("home.title")),
    el("p", {class: "hero__lede"}, t("home.lede")),
    el("p", {class: "hero__lede"}, t("home.then")),
  ]);
  const actions = el("div", {class: "hero__actions"});
  if (signedOut) actions.append(el("a", {class: "btn btn--primary", href: signInHref()}, t("home.cta.signin")), el("p", {class: "hero__why"}, t("home.signin_why")));
  else actions.append(link("/thoughts?new=1", t("home.cta.share"), {class: "btn btn--primary"}));
  actions.append(link("/connect", t("home.cta.connect"), {class: "btn btn--quiet"}));
  hero.append(actions);
  const steps = el("ol", {class: "steps"}, [1, 2, 3].map((n) => el("li", {class: "step"}, [
    el("span", {class: "step__n"}, String(n)), el("h2", {class: "step__title"}, t(`home.step${n}.title`)), el("p", {class: "step__body"}, t(`home.step${n}.body`))])));
  return el("div", {class: "landing"}, [hero, steps]);
}

function sectionHead(title, href, allLabel) {
  return el("div", {class: "section-head"}, [el("h2", {class: "section__title"}, title), href ? link(href, allLabel, {class: "section__all"}) : null]);
}

function topicOf(sessionId) {
  return store.thoughts().find((r) => r.session_id === sessionId)?.topic || "";
}

function newsSection() {
  const items = [];
  for (const alert of store.alerts().filter((a) => !a.seen_at)) {
    const who = alert.person_pseudonym || "Someone";
    const text = alert.reason === "they_arrived" ? t("home.news.arrived", {who, topic: topicOf(alert.my_session_id)}) : t("home.news.existing", {who, topic: topicOf(alert.my_session_id)});
    items.push(el("li", {class: "news__item"}, [avatar(who), el("div", {class: "news__body"}, [
      el("p", {class: "news__text"}, text),
      el("p", {class: "news__meta"}, [alert.display?.topic ? `“${alert.display.topic}” · ` : "", t("home.news.match", {score: score(alert.scores_at_detection?.structural)}), " · ", timeAgo(alert.detected_at)])]),
      el("div", {class: "news__actions"}, [
        link(`/people?thought=${encodeURIComponent(alert.my_session_id)}&select=${encodeURIComponent(alert.their_session_id)}`, t("home.news.see"), {class: "btn btn--small btn--primary",
          onclick: () => { store.write("/api/product/resonances/seen", {alert_keys: [alert.alert_key]}); }}),
        button(t("home.news.dismiss"), () => attempt(() => store.write("/api/product/resonances/dismiss", {alert_key: alert.alert_key})), {variant: "btn--small btn--quiet"})])]));
  }
  for (const row of store.intros().incoming.filter((r) => r.state === "requested")) {
    items.push(el("li", {class: "news__item"}, [avatar(row.counterpart_display), el("div", {class: "news__body"}, [el("p", {class: "news__text"}, t("home.news.request", {who: row.counterpart_display})), el("p", {class: "news__meta"}, timeAgo(row.created_at))]),
      el("div", {class: "news__actions"}, [link("/talk", t("home.news.answer"), {class: "btn btn--small btn--primary"})])]));
  }
  for (const inv of store.topics().invitations) {
    items.push(el("li", {class: "news__item"}, [avatar(inv.invited_by_pseudonym || "?"), el("div", {class: "news__body"}, [el("p", {class: "news__text"}, t("home.news.invite", {who: inv.invited_by_pseudonym || "…", title: inv.title}))]),
      el("div", {class: "news__actions"}, [link("/groups", t("home.news.answer"), {class: "btn btn--small btn--primary"})])]));
  }
  for (const g of store.topics().topics.filter((g) => Number(g.new_for_you) > 0)) {
    items.push(el("li", {class: "news__item"}, [el("span", {class: "avatar avatar--group"}, "◎"), el("div", {class: "news__body"}, [el("p", {class: "news__text"}, t("home.news.group_new", {n: Number(g.new_for_you), title: g.title}))]),
      el("div", {class: "news__actions"}, [link(`/groups/${encodeURIComponent(g.workspace_id)}`, t("home.news.open"), {class: "btn btn--small btn--primary"})])]));
  }
  if (!items.length) return el("section", {class: "news news--quiet"}, [el("p", {class: "quiet"}, t("home.quiet"))]);
  return el("section", {class: "news"}, [sectionHead(t("home.whats_new")), el("ul", {class: "news__list"}, items)]);
}

// The people found for every thought that is looking: discovery, one read
// per thought and cached, merged with what the standing search held while
// this person was away. Best match per person.
function foundPeople() {
  const best = new Map();
  const consider = (name, strength, mySession, theirSession, topic) => {
    const current = best.get(name);
    if (!current || strength > current.strength) best.set(name, {name, strength, mySession, theirSession, topic, forTopic: topicOf(mySession)});
  };
  for (const a of store.alerts()) consider(a.person_pseudonym || "Someone", Number(a.scores_at_detection?.structural) || 0, a.my_session_id, a.their_session_id, a.display?.topic || "");
  const {people, loading} = store.peopleAcross(store.discoverableThoughts().slice(0, 4).map((r) => r.session_id));
  for (const p of people) if (p.mode_classification !== "negative") consider(p.person_pseudonym, Number(p.scores?.structural) || 0, p.for_session_id, p.session_id, p.display?.topic || "");
  return {people: [...best.values()].sort((x, y) => y.strength - x.strength), loading};
}

function homePeople() {
  const {people, loading} = foundPeople();
  const box = el("section", {class: "panel dash-panel"}, [sectionHead(t("home.people"), "/people", t("home.people.all"))]);
  if (!people.length) { box.append(loading ? el("div", {class: "skeleton skeleton--row"}) : el("p", {class: "quiet"}, t("home.people.none"))); return box; }
  box.append(el("ul", {class: "person-rows"}, people.slice(0, 5).map((p) => el("li", {class: "person-row"}, [
    avatar(p.name),
    el("div", {class: "person-row__body"}, [el("span", {class: "person-row__name"}, p.name), el("span", {class: "person-row__meta"}, [p.topic ? `“${p.topic}”` : "", p.forTopic ? ` · ${t("found_for", {topic: p.forTopic})}` : ""])]),
    el("div", {class: "person-row__strength"}, [el("div", {class: "meter"}, el("div", {class: "meter__fill", style: null})), el("span", {class: "quiet"}, score(p.strength))]),
    link(`/people?thought=${encodeURIComponent(p.mySession)}&select=${encodeURIComponent(p.theirSession)}`, t("home.news.see"), {class: "btn btn--small"}),
  ]))));
  for (const [i, li] of [...box.querySelectorAll(".person-row")].entries()) li.querySelector(".meter__fill").style.width = `${Math.round(people[i].strength * 100)}%`;
  return box;
}

function homeThoughts() {
  const mine = store.thoughts();
  const counts = store.peopleCountByThought();
  const box = el("section", {class: "panel dash-panel"}, [sectionHead(t("home.thoughts"), "/thoughts", t("home.thoughts.all"))]);
  box.append(el("ul", {class: "rows"}, mine.slice(0, 5).map((r) => el("li", {class: "row-item"}, [
    stateDot(r.state),
    el("div", {class: "row-item__body"}, [link(`/people?thought=${encodeURIComponent(r.session_id)}`, thoughtTitle(r), {class: "row-item__title"}),
      el("span", {class: "row-item__meta"}, counts.get(r.session_id) ? t("thoughts.people.count", {n: counts.get(r.session_id)}) : (r.state === "discoverable" ? t("thoughts.people.none") : t(`thoughts.state.${r.state}`)))]),
  ]))));
  return box;
}

function homeGroups() {
  const {topics} = store.topics();
  const box = el("section", {class: "panel dash-panel"}, [sectionHead(t("home.groups"), "/groups", t("home.groups.all"))]);
  if (!topics.length) { box.append(el("p", {class: "quiet"}, t("groups.empty"))); return box; }
  box.append(el("ul", {class: "rows"}, topics.slice(0, 4).map((g) => el("li", {class: "row-item"}, [
    el("span", {class: "avatar avatar--group"}, "◎"),
    el("div", {class: "row-item__body"}, [link(`/groups/${encodeURIComponent(g.workspace_id)}`, g.title, {class: "row-item__title"}), el("span", {class: "row-item__meta"}, t("groups.members", {n: (g.members || []).length}))]),
    Number(g.new_for_you) > 0 ? el("span", {class: "chip chip--new"}, t("groups.new_for_you", {n: Number(g.new_for_you)})) : null,
  ]))));
  return box;
}

function homeTalks() {
  const connections = store.connections();
  const box = el("section", {class: "panel dash-panel"}, [sectionHead(t("home.talks"), "/talk", t("home.talks.all"))]);
  if (!connections.length) { box.append(el("p", {class: "quiet"}, t("talk.empty"))); return box; }
  box.append(el("ul", {class: "rows"}, connections.slice(0, 4).map((c) => el("li", {class: "row-item"}, [
    avatar(c.counterpart_display),
    el("div", {class: "row-item__body"}, [link(`/talk/${encodeURIComponent(c.intro_id)}`, c.counterpart_display, {class: "row-item__title"}), el("span", {class: "row-item__meta"}, timeAgo(c.updated_at))]),
  ]))));
  return box;
}

// ---- thoughts ------------------------------------------------------------------------------

function thoughtTitle(row) {
  const topic = String(row.topic || "").trim();
  if (topic && topic !== "Shared thought") return topic;
  const nodes = row.nodes || [];
  if (!nodes.length) return t("thoughts.structure");
  const last = row.relations?.length ? row.relations[row.relations.length - 1].to : nodes[nodes.length - 1].label;
  return last && last !== nodes[0].label ? `${nodes[0].label} → ${last}` : nodes[0].label;
}

function thoughtsView() {
  const frag = document.createDocumentFragment();
  if (store.getState().phase === "signed-out") { frag.append(landing(true)); return frag; }
  const mine = store.thoughts();
  const route = current();
  if (route.query.get("new") === "1" && !ui.composer) { ui.composer = {step: "write", text: "", preview: null, busy: false, place: null}; history.replaceState({}, "", "/thoughts"); }
  // Warm the per-thought discovery so each card can say how many people it found.
  store.peopleAcross(mine.filter((r) => r.state === "discoverable").slice(0, 6).map((r) => r.session_id));
  const countOf = (state) => mine.filter((r) => state === "all" || r.state === state).length;
  frag.append(el("header", {class: "page-head page-head--row"}, [
    el("div", {}, [el("h1", {}, t("thoughts.title")), el("p", {class: "lede"}, t("thoughts.lede"))]),
    ui.composer ? null : button(t("thoughts.new"), () => { ui.composer = {step: "write", text: "", preview: null, busy: false, place: null}; render(); }, {variant: "btn--primary"}),
  ]));
  if (ui.composer) frag.append(composer());
  if (ui.editing) frag.append(editPanel());
  if (!mine.length) { if (!ui.composer) frag.append(empty(t("thoughts.empty"))); return frag; }
  frag.append(el("div", {class: "chips", role: "tablist"}, ["all", "discoverable", "private", "withdrawn"].filter((s) => s === "all" || countOf(s)).map((s) =>
    el("button", {type: "button", role: "tab", class: `chip-tab ${ui.thoughtsFilter === s ? "is-on" : ""}`, "aria-selected": String(ui.thoughtsFilter === s), onclick: () => { ui.thoughtsFilter = s; render(); }},
      [s === "all" ? t("thoughts.filter.all") : t(`thoughts.state.${s}`), el("span", {class: "chip-tab__n"}, String(countOf(s)))]))));
  const shown = mine.filter((r) => ui.thoughtsFilter === "all" || r.state === ui.thoughtsFilter);
  frag.append(el("ul", {class: "card-grid"}, shown.map(thoughtCard)));
  return frag;
}

function thoughtCard(row) {
  const counts = store.peopleCountByThought();
  const found = counts.get(row.session_id) || 0;
  const when = row.state === "discoverable" ? t("thoughts.shared_at", {when: timeAgo(row.shared_at)})
    : row.state === "withdrawn" ? t("thoughts.withdrawn_at", {when: timeAgo(row.withdrawn_at)}) : t("thoughts.prepared_at", {when: timeAgo(row.prepared_at)});
  const card = el("li", {class: `card thought thought--${row.state}`});
  const actions = [
    [t("thoughts.edit"), () => openEditor(row)],
    row.state !== "discoverable" ? [shareWord(row), () => shareAgain(row)] : null,
    row.state === "discoverable" ? [t("thoughts.stop"), () => { ui.stopAsk = row.session_id; render(); }] : null,
    [t("thoughts.delete"), () => { ui.deleteAsk = row.session_id; render(); }, true],
  ];
  card.append(el("div", {class: "card__head"}, [el("span", {class: "state"}, [stateDot(row.state), t(`thoughts.state.${row.state}`)]), el("span", {class: "card__when"}, when), menu(row.session_id, actions)]));
  card.append(el("h2", {class: "card__title"}, thoughtTitle(row)));
  card.append(el("p", {class: "card__meta"}, [row.domain ? el("span", {class: "pill"}, row.domain) : null, " ", t("thoughts.ideas", {n: row.nodes?.length || 0}), " · ", t("thoughts.links", {n: row.relations?.length || 0}),
    row.state === "discoverable" ? [" · ", el("strong", {}, found ? t("thoughts.people.count", {n: found}) : t("thoughts.people.none"))] : null]));
  card.append(disclosure(`structure:${row.session_id}`, t("thoughts.structure"), structure(row.nodes, row.relations)));
  const foot = el("div", {class: "card__actions"});
  if (ui.stopAsk === row.session_id) {
    foot.append(el("div", {class: "confirm"}, [el("p", {}, t("thoughts.stop.confirm")),
      el("div", {class: "row"}, [button(t("thoughts.stop.yes"), async () => { ui.stopAsk = null; await attempt(() => store.write("/api/product/revoke", {session_id: row.session_id, request_id: store.requestId("stop"), confirmed: true}, {invalidate: {discovery: true}})); }, {variant: "btn--small btn--danger"}),
        button(t("thoughts.stop.no"), () => { ui.stopAsk = null; render(); }, {variant: "btn--small btn--quiet"})])]));
  } else if (ui.deleteAsk === row.session_id) {
    foot.append(el("div", {class: "confirm"}, [el("p", {}, t("thoughts.delete.confirm")),
      el("div", {class: "row"}, [button(t("thoughts.delete.yes"), async () => { ui.deleteAsk = null; await attempt(() => store.write("/api/product/delete", {session_id: row.session_id, confirmed: true}, {invalidate: {discovery: true}})); }, {variant: "btn--small btn--danger"}),
        button(t("cancel"), () => { ui.deleteAsk = null; render(); }, {variant: "btn--small btn--quiet"})])]));
  } else if (row.state === "discoverable") {
    foot.append(link(`/people?thought=${encodeURIComponent(row.session_id)}`, t("thoughts.people"), {class: "btn btn--small btn--primary"}));
  } else {
    foot.append(button(shareWord(row), () => shareAgain(row), {variant: "btn--small btn--primary"}));
  }
  card.append(foot);
  return card;
}

function shareWord(row) { return row.state === "withdrawn" ? t("thoughts.share_again") : t("thoughts.composer.share"); }

// The stored structure as the graph the prepare route takes.
function graphOf(row, {title, domain, nodes, relations} = {}) {
  const ns = (nodes || row.nodes || []).map((n, i) => ({id: `n${i}`, label: n.label, role: n.role || "state"}));
  const indexOf = (label) => ns.findIndex((n) => n.label === label);
  const rs = (relations || row.relations || []).map((r) => ({source: `n${indexOf(r.from)}`, target: `n${indexOf(r.to)}`, type: r.type})).filter((r) => r.source !== "n-1" && r.target !== "n-1");
  return {topic: title ?? row.topic, domain: domain ?? row.domain, nodes: ns, relations: rs};
}

async function prepareAndShare(graph, {share = true} = {}) {
  await store.write("/api/webmcp/prepare", {request_id: store.requestId("prep"), thought: graph, authorship: "their_own_words"});
  if (!share) return true;
  const preview = await fetch("/api/webmcp/preview", {credentials: "same-origin", cache: "no-store"}).then((r) => r.json());
  if (!preview?.confirmation_token) throw new Error(preview?.message || t("thoughts.composer.nothing"));
  await store.write("/api/webmcp/share", {request_id: store.requestId("share"), confirm: true, confirmation_token: preview.confirmation_token}, {invalidate: {discovery: true}});
  return true;
}

async function shareAgain(row) {
  const done = await attempt(() => prepareAndShare(graphOf(row)));
  if (done) {
    if (row.state === "private") await attempt(() => store.write("/api/product/delete", {session_id: row.session_id, confirmed: true}));
    toast(t("thoughts.composer.share"));
    await store.load();
    navigate("/people");
  }
}

function openEditor(row) {
  ui.editing = {session_id: row.session_id, state: row.state, title: row.topic || "", domain: row.domain || "",
    nodes: (row.nodes || []).map((n) => ({label: n.label, role: n.role || "state"})),
    relations: (row.relations || []).map((r) => ({from: r.from, type: r.type, to: r.to})),
    original: JSON.stringify([row.nodes, row.relations]), busy: false};
  render();
  document.getElementById("edit-title")?.focus();
}

const RELATION_TYPES = ["causes", "prevents", "requires", "supports", "constrains", "contradicts", "part_of"];

function editPanel() {
  const e = ui.editing;
  const box = el("section", {class: "panel composer", "aria-label": t("thoughts.edit.title")});
  box.append(el("h2", {class: "panel__title"}, t("thoughts.edit.title")));
  box.append(el("div", {class: "form-grid"}, [
    el("label", {class: "field"}, [el("span", {class: "label"}, t("thoughts.edit.name")), el("input", {id: "edit-title", type: "text", maxLength: 120, value: e.title, oninput: (ev) => { e.title = ev.target.value; }})]),
    el("label", {class: "field"}, [el("span", {class: "label"}, t("thoughts.edit.field")), el("input", {type: "text", maxLength: 60, value: e.domain, oninput: (ev) => { e.domain = ev.target.value; }})]),
  ]));
  const ideas = el("div", {class: "edit-list"}, [el("span", {class: "label"}, t("thoughts.edit.ideas"))]);
  e.nodes.forEach((n, i) => ideas.append(el("div", {class: "edit-row"}, [
    el("input", {type: "text", maxLength: 120, value: n.label, oninput: (ev) => { const old = n.label; n.label = ev.target.value; for (const r of e.relations) { if (r.from === old) r.from = n.label; if (r.to === old) r.to = n.label; } }}),
    el("select", {onchange: (ev) => { n.role = ev.target.value; }}, ["problem", "mechanism", "outcome", "method", "constraint", "resource", "state", "evidence", "agent"].map((role) => el("option", {value: role, selected: role === n.role}, role))),
    button("×", () => { e.relations = e.relations.filter((r) => r.from !== n.label && r.to !== n.label); e.nodes.splice(i, 1); render(); }, {variant: "btn--small btn--quiet", title: t("thoughts.edit.remove")}),
  ])));
  ideas.append(button(t("thoughts.edit.add_idea"), () => { e.nodes.push({label: "", role: "state"}); render(); }, {variant: "btn--small"}));
  const links = el("div", {class: "edit-list"}, [el("span", {class: "label"}, t("thoughts.edit.links"))]);
  const labels = () => e.nodes.map((n) => n.label).filter(Boolean);
  e.relations.forEach((r, i) => links.append(el("div", {class: "edit-row edit-row--link"}, [
    el("select", {onchange: (ev) => { r.from = ev.target.value; }}, labels().map((l) => el("option", {value: l, selected: l === r.from}, l))),
    el("select", {onchange: (ev) => { r.type = ev.target.value; }}, RELATION_TYPES.map((k) => el("option", {value: k, selected: k === r.type}, relationWord(k)))),
    el("select", {onchange: (ev) => { r.to = ev.target.value; }}, labels().map((l) => el("option", {value: l, selected: l === r.to}, l))),
    button("×", () => { e.relations.splice(i, 1); render(); }, {variant: "btn--small btn--quiet", title: t("thoughts.edit.remove")}),
  ])));
  links.append(button(t("thoughts.edit.add_link"), () => { const ls = labels(); e.relations.push({from: ls[0] || "", type: "causes", to: ls[1] || ls[0] || ""}); render(); }, {variant: "btn--small"}));
  box.append(ideas, links, el("p", {class: "hint"}, t("thoughts.edit.hint")));
  box.append(el("div", {class: "row"}, [
    button(t("save"), () => saveEdit(), {variant: "btn--primary", disabled: e.busy}),
    button(t("cancel"), () => { ui.editing = null; render(); }, {variant: "btn--quiet"}),
  ]));
  return box;
}

async function saveEdit() {
  const e = ui.editing;
  const row = store.thoughts().find((r) => r.session_id === e.session_id);
  if (!row) { ui.editing = null; render(); return; }
  e.busy = true; render();
  const nodes = e.nodes.filter((n) => n.label.trim());
  const relations = e.relations.filter((r) => r.from && r.to && r.from !== r.to);
  const structureChanged = JSON.stringify([nodes.map((n) => ({label: n.label, role: n.role})), relations]) !== JSON.stringify([(row.nodes || []).map((n) => ({label: n.label, role: n.role || "state"})), (row.relations || []).map((r) => ({from: r.from, type: r.type, to: r.to}))]);
  const done = await attempt(async () => {
    if (!structureChanged) {
      await store.write("/api/product/metadata", {session_id: row.session_id, presentation: {topic: e.title.trim() || row.topic, domain: e.domain.trim() || row.domain || "general", cluster_id: (e.title || row.topic || "shared").toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 48)}}, {invalidate: {discovery: true}});
      return true;
    }
    const graph = graphOf(row, {title: e.title.trim() || row.topic, domain: e.domain.trim() || row.domain || "general", nodes, relations});
    await prepareAndShare(graph, {share: row.state === "discoverable"});
    if (row.state === "discoverable") await store.write("/api/product/revoke", {session_id: row.session_id, request_id: store.requestId("stop"), confirmed: true}, {invalidate: {discovery: true}});
    else await store.write("/api/product/delete", {session_id: row.session_id, confirmed: true});
    return true;
  });
  e.busy = false;
  if (done) { ui.editing = null; toast(t("thoughts.edit.saved")); await store.load(); }
  render();
}

function composer() {
  const c = ui.composer;
  const box = el("section", {class: "panel composer", "aria-label": t("thoughts.new")});
  if (c.step === "write") {
    const area = el("textarea", {id: "compose-text", rows: 6, maxLength: 4000, placeholder: t("thoughts.composer.placeholder"), value: c.text, oninput: (e) => { c.text = e.target.value; }});
    const status = el("p", {class: `status ${c.error ? "status--error" : ""}`, role: "status"}, c.busy ? t("thoughts.composer.reading") : (c.error || ""));
    const place = el("div", {class: "place-row"});
    const placeToggle = el("input", {type: "checkbox", id: "compose-place", checked: !!c.place});
    placeToggle.addEventListener("change", async () => {
      if (!placeToggle.checked) { c.place = null; render(); return; }
      try {
        const pos = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, {timeout: 8000}));
        c.place = {lat: Math.round(pos.coords.latitude * 10) / 10, lon: Math.round(pos.coords.longitude * 10) / 10};
      } catch { c.place = null; placeToggle.checked = false; notice(t("thoughts.place.denied")); }
      render();
    });
    place.append(el("label", {for: "compose-place", class: "check"}, [placeToggle, " ", t("thoughts.place.offer")]));
    if (c.place) place.append(el("div", {class: "form-grid"}, [draftField("input", "compose-city", {type: "text", maxLength: 80, placeholder: t("thoughts.place.city")}), draftField("input", "compose-region", {type: "text", maxLength: 80, placeholder: t("thoughts.place.region")})]),
      el("p", {class: "hint"}, t("thoughts.place.hint", {lat: c.place.lat, lon: c.place.lon})));
    const submit = button(t("thoughts.composer.extract"), async () => {
      if (!c.text.trim()) { area.focus(); return; }
      c.busy = true; c.error = ""; render();
      try {
        const where = c.place && (ui.drafts["compose-city"] || "").trim()
          ? {lat: c.place.lat, lon: c.place.lon, city: (ui.drafts["compose-city"] || "").trim(), region: (ui.drafts["compose-region"] || "").trim() || "—"} : undefined;
        // This is the person, typing into their own page: there is no
        // assistant between the words and the author, so the page states it.
        await store.write("/api/webmcp/prepare", {request_id: store.requestId("prep"), context: c.text, authorship: "their_own_words", coarse_location: where});
        const preview = await fetch("/api/webmcp/preview", {credentials: "same-origin", cache: "no-store"}).then((r) => r.json());
        if (!preview?.confirmation_token) throw new Error(preview?.message || t("thoughts.composer.nothing"));
        c.preview = preview; c.step = "preview";
      } catch (error) { c.error = error.message; }
      c.busy = false; render();
    }, {variant: "btn--primary", disabled: c.busy});
    box.append(el("label", {for: "compose-text", class: "label"}, t("thoughts.composer.label")), area, el("p", {class: "hint"}, t("thoughts.composer.hint")), place,
      el("div", {class: "row"}, [submit, button(t("cancel"), () => { ui.composer = null; render(); }, {variant: "btn--quiet"})]), status);
    return box;
  }
  const shown = c.preview.will_become_discoverable?.thought || {};
  const status = el("p", {class: `status ${c.error ? "status--error" : ""}`, role: "status"}, c.error || "");
  box.append(el("h2", {class: "panel__title"}, t("thoughts.composer.preview")), structure(shown.nodes || [], shown.relations || []),
    el("div", {class: "row"}, [
      button(t("thoughts.composer.share"), async () => {
        c.busy = true; render();
        try {
          await store.write("/api/webmcp/share", {request_id: store.requestId("share"), confirm: true, confirmation_token: c.preview.confirmation_token}, {invalidate: {discovery: true}});
          ui.composer = null;
          await store.load();
          const newest = store.discoverableThoughts()[0];
          navigate(newest ? `/people?thought=${encodeURIComponent(newest.session_id)}` : "/thoughts");
          return;
        } catch (error) { c.error = error.message; c.busy = false; render(); }
      }, {variant: "btn--primary", disabled: c.busy}),
      button(t("thoughts.composer.back"), () => { c.step = "write"; c.preview = null; c.error = ""; render(); }, {variant: "btn--quiet"}),
    ]), status);
  return box;
}

// ---- people ------------------------------------------------------------------------------------

function peopleView() {
  const frag = document.createDocumentFragment();
  if (store.getState().phase === "signed-out") { frag.append(landing(true)); return frag; }
  const shared = store.discoverableThoughts();
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("people.title")), el("p", {class: "lede"}, t("people.lede"))]));
  if (!shared.length) {
    frag.append(empty(t("people.none_shared"), "", link("/thoughts?new=1", t("thoughts.new"), {class: "btn btn--primary"})));
    return frag;
  }
  const route = current();
  const asked = route.query.get("thought");
  if (asked && shared.some((r) => r.session_id === asked)) ui.peopleFilter = asked;
  if (ui.peopleFilter !== "all" && !shared.some((r) => r.session_id === ui.peopleFilter)) ui.peopleFilter = "all";
  const active = ui.peopleFilter === "all" ? shared : shared.filter((r) => r.session_id === ui.peopleFilter);
  if (shared.length > 1) {
    frag.append(el("div", {class: "chips", role: "tablist"}, [["all", t("people.filter.all")], ...shared.map((r) => [r.session_id, thoughtTitle(r)])].map(([key, label]) =>
      el("button", {type: "button", role: "tab", class: `chip-tab ${ui.peopleFilter === key ? "is-on" : ""}`, "aria-selected": String(ui.peopleFilter === key), onclick: () => { ui.peopleFilter = key; history.replaceState({}, "", key === "all" ? "/people" : `/people?thought=${encodeURIComponent(key)}`); render(); }}, label))));
  } else {
    frag.append(el("p", {class: "quiet"}, t("found_for", {topic: thoughtTitle(shared[0])})));
  }
  const {people, loading, error} = store.peopleAcross(active.map((r) => r.session_id));
  const wanted = route.query.get("select");
  if (wanted && people.some((p) => p.session_id === wanted)) { ui.peopleSelected = wanted; ui.drawer = {kind: "person", id: wanted}; history.replaceState({}, "", `/people${ui.peopleFilter === "all" ? "" : `?thought=${encodeURIComponent(ui.peopleFilter)}`}`); }
  if (loading && !people.length) { frag.append(el("div", {class: "skeleton-grid"}, [el("div", {class: "skeleton skeleton--map"}), el("div", {class: "skeleton"}), el("div", {class: "skeleton"})])); return frag; }
  const resonating = people.filter((p) => p.mode_classification !== "negative");
  const near = people.filter((p) => p.mode_classification === "negative");
  if (error && !people.length) {
    frag.append(el("div", {class: "status status--error"}, [t("people.error", {message: error}), " ", button(t("error.retry"), () => { store.retryDiscovery(active.map((r) => r.session_id)); render(); }, {variant: "btn--small"})]));
  } else if (!resonating.length) {
    frag.append(empty(t("people.empty.title"), t("people.empty.body")));
  } else {
    frag.append(el("div", {class: "people-layout"}, [
      el("div", {class: "people-viz"}, vizPanel(resonating, near, active)),
      el("div", {class: "people-list"}, [el("p", {class: "count"}, t("people.found", {n: resonating.length})), el("ol", {class: "person-cards"}, resonating.map(personCard))]),
    ]));
  }
  if (near.length) {
    frag.append(disclosure("near", [t("people.near", {n: near.length}), " ", el("span", {class: "quiet"}, t("people.near.hint"))],
      el("ul", {class: "near__list"}, near.map((m) => el("li", {}, [avatar(m.person_pseudonym, "avatar--small"), " ", el("strong", {}, m.person_pseudonym), " · ", m.display?.topic || "", " · ", el("span", {class: "quiet"}, m.hard_rejection ? rejectionWords(m.hard_rejection) : verdict(m.mode_classification))]))))); 
  }
  frag.append(connectionsSection());
  if (ui.drawer?.kind === "person") {
    const person = people.find((p) => p.session_id === ui.drawer.id);
    if (person) frag.append(personDrawer(person));
  }
  return frag;
}

function rejectionWords(reason) {
  const kind = String(reason || "").split(":")[0];
  if (kind === "direction") return t("people.reject.direction");
  if (kind === "relation_type") return t("people.reject.relation_type");
  return t("people.reject.other");
}

function selectPerson(id) {
  ui.peopleSelected = id;
  ui.drawer = {kind: "person", id};
  render();
}

function vizPanel(people, near, thoughts) {
  const panel = el("section", {class: "panel viz", "aria-label": t("people.map")});
  const views = [["constellation", t("people.map.strength")], ["where", t("people.map.where")]];
  if (thoughts.length > 1) views.push(["matrix", "Matrix"]);
  if (ui.peopleView === "matrix" && thoughts.length < 2) ui.peopleView = "constellation";
  panel.append(el("div", {class: "tabs", role: "tablist"}, views.map(([key, label]) =>
    el("button", {type: "button", role: "tab", class: "tab", "aria-selected": String(ui.peopleView === key), onclick: () => { ui.peopleView = key; render(); }}, label))));
  if (ui.peopleView === "constellation") {
    const centres = thoughts.map((r) => ({id: r.session_id, label: thoughtTitle(r)}));
    const nodes = [...people, ...near].map((p) => ({id: p.session_id, name: p.person_pseudonym, kind: p.mode_classification, strength: Number(p.scores?.structural) || 0, depth: p.evidence?.mapped_node_count || 0, topic: p.display?.topic || "", links: p.evidence?.preserved_relation_count || 0}));
    const links = [];
    for (const p of [...people, ...near]) {
      links.push({source: p.for_session_id, target: p.session_id, strength: Number(p.scores?.structural) || 0, kind: p.mode_classification, contradictions: p.evidence?.contradiction_count || 0});
      for (const o of p.others || []) links.push({source: o.for_session_id, target: p.session_id, strength: Number(o.scores?.structural) || 0, kind: o.mode_classification, contradictions: o.evidence?.contradiction_count || 0});
    }
    panel.append(el("div", {class: "map-frame"}, constellation({centres, people: nodes, links}, {selected: ui.peopleSelected, onSelect: selectPerson})));
    const kinds = new Map();
    for (const p of [...people, ...near]) kinds.set(p.mode_classification, (kinds.get(p.mode_classification) || 0) + 1);
    panel.append(el("ul", {class: "map-legend"}, [...kinds].map(([kind, n]) => el("li", {}, [el("span", {class: `swatch swatch--${kind}`}), `${verdict(kind)} · ${n}`]))));
    panel.append(el("p", {class: "hint"}, t("people.map.strength.hint")));
  } else if (ui.peopleView === "where") {
    const first = thoughts[0]?.session_id;
    const entry = store.getState().geo.get(first);
    if (!entry) store.geo(first);
    if (!entry || (entry.loading && !entry.payload)) { panel.append(el("div", {class: "skeleton skeleton--map"})); return panel; }
    if (!entry.payload) { panel.append(el("p", {class: "status status--error"}, entry.error || "")); return panel; }
    const {svg, placed, unplaced} = worldMap(entry.payload, {selected: ui.peopleSelected, onSelect: selectPerson});
    panel.append(el("div", {class: "map-frame map-frame--world"}, svg));
    const lines = [];
    if (!entry.payload.you) lines.push(t("people.map.you_unplaced"));
    // One person can be found through two of their thoughts: name them once.
    const names = [...new Set(unplaced.map((p) => p.name))];
    if (names.length) lines.push(t("people.map.unplaced", {n: names.length, names: names.join(", ")}));
    if (!placed.length && !unplaced.length) lines.push(t("people.map.nobody"));
    lines.push(t("people.map.where.hint"));
    panel.append(el("p", {class: "hint"}, lines.join(" ")));
  } else {
    // Rows: the people who resonate with at least one thought. A near miss
    // everywhere is not a row; the disclosure below lists those.
    const rows = people.map((p) => ({id: p.session_id, name: p.person_pseudonym, all: [p, ...(p.others || [])]}));
    panel.append(el("div", {class: "heat-wrap"}, heatmap({thoughts: thoughts.map((r) => ({id: r.session_id, label: thoughtTitle(r)})), people: rows,
      cell: (p, th) => { const m = p.all.find((x) => x.for_session_id === th.id); return m ? {strength: Number(m.scores?.structural) || 0, kind: verdict(m.mode_classification), near: m.mode_classification === "negative"} : null; }},
      {selected: ui.peopleSelected, onSelect: selectPerson})));
  }
  return panel;
}

function personCard(p) {
  const selected = p.session_id === ui.peopleSelected;
  const existing = store.introFor(p.session_id);
  const card = el("li", {class: `person ${selected ? "is-selected" : ""}`});
  const open = el("button", {type: "button", class: "person__open", "aria-pressed": String(selected), onclick: () => selectPerson(p.session_id)}, [
    avatar(p.person_pseudonym, "avatar--big"),
    el("div", {class: "person__body"}, [
      el("div", {class: "person__top"}, [el("span", {class: "person__name"}, p.person_pseudonym), p.display?.domain ? el("span", {class: "pill"}, p.display.domain) : null,
        existing?.state === "accepted" ? el("span", {class: "chip chip--ok"}, t("people.connected")) : null]),
      el("p", {class: "person__topic"}, p.display?.topic || ""),
      el("p", {class: "person__verdict"}, [verdict(p.mode_classification), ui.peopleFilter === "all" && store.discoverableThoughts().length > 1 && p.for_topic ? el("span", {class: "quiet"}, ` · ${t("found_for", {topic: p.for_topic})}`) : null]),
      profile(p.scores),
      el("p", {class: "person__depth"}, t("people.depth", {nodes: p.evidence?.mapped_node_count || 0, total: p.for_nodes || 0, links: p.evidence?.preserved_relation_count || 0})),
      p.display?.demo_persona ? el("p", {class: "quiet"}, t("people.example")) : null,
    ]),
    el("span", {class: "person__score"}, [el("strong", {}, score(p.scores?.structural)), el("span", {class: "quiet"}, strengthWord(p.scores?.structural))]),
  ]);
  card.append(open);
  return card;
}

function personDrawer(p) {
  const closeIt = () => { ui.drawer = null; render(); };
  const backdrop = el("div", {class: "drawer-backdrop", onclick: closeIt});
  const drawer = el("aside", {class: "drawer", role: "dialog", "aria-label": p.person_pseudonym});
  drawer.append(el("div", {class: "drawer__head"}, [avatar(p.person_pseudonym, "avatar--big"), el("div", {}, [el("h2", {class: "drawer__title"}, p.person_pseudonym), el("p", {class: "quiet"}, [p.display?.topic || "", p.display?.domain ? ` · ${p.display.domain}` : ""])]),
    button("×", closeIt, {variant: "btn--quiet btn--small", title: t("close")})]));
  const versions = [p, ...(p.others || [])];
  for (const m of versions) drawer.append(evidenceBlock(m, versions.length > 1));
  drawer.append(introAction(p));
  document.addEventListener("keydown", function onKey(e) { if (e.key === "Escape") { document.removeEventListener("keydown", onKey); closeIt(); } });
  return el("div", {class: "drawer-host"}, [backdrop, drawer]);
}

function evidenceBlock(m, named) {
  const box = el("section", {class: "evidence"});
  box.append(el("p", {class: "eyebrow"}, named ? t("found_for", {topic: m.for_topic}) : t("people.why")),
    el("p", {class: "evidence__verdict"}, [verdict(m.mode_classification), " · ", t(`people.confidence.${m.confidence || "medium"}`)]),
    profile(m.scores),
    el("p", {class: "evidence__score"}, [t("people.depth", {nodes: m.evidence?.mapped_node_count || 0, total: m.for_nodes || 0, links: m.evidence?.preserved_relation_count || 0}),
      (m.evidence?.contradiction_count || 0) > 0 ? ` · ${t("people.contradictions", {n: m.evidence.contradiction_count})}` : ""]));
  const ctx = store.getState().context.get(m.for_session_id);
  if (!ctx) store.context(m.for_session_id);
  const mineNodes = ctx?.payload?.active_thought?.nodes || [];
  const mineRelations = ctx?.payload?.active_thought?.relations || [];
  const pairs = (m.evidence?.top_correspondences || []).map((c) => ({mine: c.query_node, theirs: c.candidate_node, mineLabel: c.query_label, theirsLabel: c.candidate_label}));
  const mine = mineNodes.length ? mineNodes.map((n) => ({id: n.id, label: n.label})) : pairs.map((c) => ({id: c.mine, label: c.mineLabel}));
  const theirs = pairs.map((c) => ({id: c.theirs, label: c.theirsLabel}));
  const keptIds = new Set((m.evidence?.preserved_relations || []).map((r) => r.query_relation));
  const kept = mineRelations.filter((r) => keptIds.has(r.id)).map((r) => ({source: r.source, target: r.target, type: r.type}));
  box.append(el("p", {class: "label"}, t("people.correspond")), el("div", {class: "corr-frame"}, correspondence({mine, theirs, pairs, keptRelations: kept})));
  return box;
}

function introAction(m) {
  const wrap = el("div", {class: "drawer__actions"});
  if (m.display?.demo_persona) return wrap;
  const existing = store.introFor(m.session_id);
  if (existing?.state === "accepted") { wrap.append(el("span", {class: "chip chip--ok"}, t("people.connected")), link(`/talk/${encodeURIComponent(existing.intro_id)}`, t("people.open_talk"), {class: "btn btn--primary"})); return wrap; }
  if (existing?.state === "requested" || ui.askSent.has(m.session_id)) { wrap.append(el("span", {class: "chip"}, t("people.asked"))); return wrap; }
  if (existing?.state === "declined") { wrap.append(el("span", {class: "chip chip--muted"}, t("people.declined"))); return wrap; }
  if (ui.askOpen !== m.session_id) { wrap.append(button(t("people.ask"), () => { ui.askOpen = m.session_id; render(); }, {variant: "btn--primary"})); return wrap; }
  const area = draftField("textarea", "ask-text", {rows: 4, maxLength: 500, placeholder: t("people.ask.placeholder")});
  wrap.append(el("label", {for: "ask-text", class: "label"}, t("people.ask.label", {who: m.person_pseudonym})), area,
    el("div", {class: "row"}, [
      button(t("people.ask.send"), async () => {
        const message = area.value.trim();
        if (!message) { area.focus(); return; }
        const done = await attempt(() => store.write("/api/product/intro/request", {request_id: store.requestId("intro"), confirmed: true, from_session_id: m.for_session_id, target_session_id: m.session_id, message}));
        if (done) { clearDraft("ask-text"); ui.askSent.add(m.session_id); ui.askOpen = null; toast(t("people.ask.sent")); render(); }
      }, {variant: "btn--primary"}),
      button(t("cancel"), () => { ui.askOpen = null; render(); }, {variant: "btn--quiet"})]));
  return wrap;
}

function connectionsSection() {
  const connections = store.connections();
  const box = el("section", {class: "connections"}, [el("h2", {class: "section__title"}, t("people.connections"))]);
  if (!connections.length) { box.append(el("p", {class: "quiet"}, t("people.connections.none"))); return box; }
  box.append(el("ul", {class: "person-rows"}, connections.map((c) => el("li", {class: "person-row"}, [avatar(c.counterpart_display), el("div", {class: "person-row__body"}, [el("span", {class: "person-row__name"}, c.counterpart_display), el("span", {class: "person-row__meta"}, timeAgo(c.updated_at))]),
    link(`/talk/${encodeURIComponent(c.intro_id)}`, t("people.open_talk"), {class: "btn btn--small"})]))));
  return box;
}

// ---- talk -----------------------------------------------------------------------------------------

function talkView() {
  const frag = document.createDocumentFragment();
  if (store.getState().phase === "signed-out") { frag.append(landing(true)); return frag; }
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("talk.title")), el("p", {class: "lede"}, t("talk.lede"))]));
  const {incoming, outgoing} = store.intros();
  const pending = [...incoming.filter((r) => r.state === "requested"), ...outgoing.filter((r) => r.state === "requested")];
  if (pending.length) frag.append(el("section", {class: "requests"}, [el("h2", {class: "section__title"}, t("talk.requests")), el("ul", {class: "cards"}, pending.map(requestCard))]));
  const connections = store.connections();
  const route = current();
  const selectedId = route.param || (connections[0]?.intro_id ?? null);
  const selected = connections.find((c) => c.intro_id === selectedId) || null;
  if (!connections.length) { frag.append(empty(t("talk.empty"), "", link("/people", t("nav.people"), {class: "btn btn--primary"}))); return frag; }
  const list = el("ul", {class: "convo-list"}, connections.map((c) => el("li", {}, link(`/talk/${encodeURIComponent(c.intro_id)}`,
    [avatar(c.counterpart_display), el("span", {class: "convo__who"}, c.counterpart_display), el("span", {class: "convo__when"}, timeAgo(c.updated_at))],
    {class: `convo ${selected?.intro_id === c.intro_id ? "is-selected" : ""}`}))));
  frag.append(el("div", {class: "split split--talk"}, [el("aside", {}, [el("h2", {class: "section__title"}, t("talk.list")), list]), el("section", {class: "thread"}, selected ? threadPanel(selected) : el("p", {class: "quiet"}, t("talk.pick")))]));
  return frag;
}

function requestCard(row) {
  const incoming = row.direction === "incoming";
  const card = el("li", {class: "card request"}, [
    el("div", {class: "card__head"}, [avatar(row.counterpart_display), el("p", {class: "card__title"}, incoming ? t("talk.incoming", {who: row.counterpart_display}) : t("talk.outgoing", {who: row.counterpart_display})), el("span", {class: "card__when"}, timeAgo(row.created_at))]),
    el("blockquote", {class: "their-words"}, row.message)]);
  const actions = el("div", {class: "card__actions"});
  if (incoming) {
    actions.append(button(t("talk.accept"), () => attempt(() => store.write("/api/product/intro/respond", {intro_id: row.intro_id, accept: true, confirmed: true, request_id: store.requestId("acc")})), {variant: "btn--small btn--primary"}),
      button(t("talk.decline"), () => attempt(() => store.write("/api/product/intro/respond", {intro_id: row.intro_id, accept: false, confirmed: true, request_id: store.requestId("dec")})), {variant: "btn--small btn--quiet"}));
  } else {
    actions.append(el("span", {class: "chip"}, t("talk.waiting")), button(t("talk.cancel"), () => attempt(() => store.write("/api/product/intro/cancel", {intro_id: row.intro_id, confirmed: true, request_id: store.requestId("can")})), {variant: "btn--small btn--quiet"}));
  }
  card.append(actions);
  return card;
}

function threadPanel(intro) {
  const box = el("div", {class: "thread__box"});
  if (!ui.talkThread || ui.talkThread.channel_id !== intro.channel_id) { ui.talkThread = {channel_id: intro.channel_id, messages: null}; loadThread(intro.channel_id); }
  const messages = ui.talkThread?.messages;
  box.append(el("header", {class: "thread__head"}, [avatar(intro.counterpart_display, "avatar--big"), el("div", {}, [el("h2", {class: "section__title"}, intro.counterpart_display), el("p", {class: "quiet"}, t("talk.relay"))])]));
  const list = el("ol", {class: "messages"});
  if (messages === null || messages === undefined) list.append(el("li", {class: "quiet"}, t("loading")));
  else if (!messages.length) list.append(el("li", {class: "quiet"}, t("talk.nothing_yet")));
  else for (const m of messages) list.append(el("li", {class: `message ${m.author === "me" ? "message--me" : ""}`}, [el("span", {class: "message__who"}, m.author === "me" ? t("talk.you") : m.author_display), el("p", {class: "message__body"}, m.body), el("span", {class: "message__when"}, timeAgo(m.created_at))]));
  box.append(list);
  const area = draftField("textarea", `talk-${intro.channel_id}`, {rows: 2, maxLength: 2000, placeholder: t("talk.placeholder", {who: intro.counterpart_display})});
  const send = button(t("talk.send"), async () => {
    const body = area.value.trim();
    if (!body) return;
    send.disabled = true;
    const done = await attempt(() => store.write("/api/product/channel/send", {channel_id: intro.channel_id, body, confirmed: true, request_id: store.requestId("msg")}));
    send.disabled = false;
    if (done) { clearDraft(`talk-${intro.channel_id}`); area.value = ""; loadThread(intro.channel_id); }
  }, {variant: "btn--primary"});
  area.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send.click(); });
  box.append(el("div", {class: "compose-row"}, [area, send]));
  box.append(el("p", {class: "quiet"}, link("/groups", t("talk.open_group", {who: intro.counterpart_display}), {onclick: () => { ui.newGroup = {introId: intro.intro_id, title: "", brief: ""}; }})));
  return box;
}

async function loadThread(channelId) {
  try {
    const payload = await store.messages(channelId);
    if (ui.talkThread?.channel_id === channelId) { ui.talkThread.messages = payload.messages || []; render(); }
  } catch (error) {
    if (ui.talkThread?.channel_id === channelId) { ui.talkThread.messages = []; render(); }
    notice(t("error.generic", {message: error.message}));
  }
}

// ---- groups -----------------------------------------------------------------------------------------

function groupsView() {
  const frag = document.createDocumentFragment();
  if (store.getState().phase === "signed-out") { frag.append(landing(true)); return frag; }
  const {topics, invitations} = store.topics();
  const connections = store.connections();
  frag.append(el("header", {class: "page-head page-head--row"}, [el("div", {}, [el("h1", {}, t("groups.title")), el("p", {class: "lede"}, t("groups.lede"))]),
    ui.newGroup ? null : button(t("groups.new"), () => { ui.newGroup = {introId: connections[0]?.intro_id || "", title: "", brief: ""}; render(); }, {variant: "btn--primary", disabled: !connections.length})]));
  if (!connections.length && !ui.newGroup) frag.append(el("p", {class: "hint"}, t("groups.new.none")));
  if (invitations.length) {
    frag.append(el("section", {}, [el("h2", {class: "section__title"}, t("groups.invitations")), el("ul", {class: "cards"}, invitations.map((inv) =>
      el("li", {class: "card"}, [el("div", {class: "card__head"}, [avatar(inv.invited_by_pseudonym || "?"), el("p", {class: "card__title"}, t("groups.invite.line", {who: inv.invited_by_pseudonym || "…", title: inv.title}))]),
        el("div", {class: "card__actions"}, [
          button(t("groups.invite.join"), () => attempt(() => store.write("/api/product/workspace/respond", {workspace_id: inv.workspace_id, accept: true, confirmed: true}, {invalidate: {groups: true}})), {variant: "btn--small btn--primary"}),
          button(t("groups.invite.later"), () => attempt(() => store.write("/api/product/workspace/respond", {workspace_id: inv.workspace_id, accept: false, confirmed: true})), {variant: "btn--small btn--quiet"})])])))]));
  }
  if (ui.newGroup) frag.append(newGroupForm());
  if (!topics.length) { if (!ui.newGroup) frag.append(empty(t("groups.empty"))); return frag; }
  frag.append(el("ul", {class: "card-grid"}, topics.map((g) => el("li", {class: "card group-card"}, [
    el("div", {class: "card__head"}, [el("h2", {class: "card__title"}, link(`/groups/${encodeURIComponent(g.workspace_id)}`, g.title)), Number(g.new_for_you) > 0 ? el("span", {class: "chip chip--new"}, t("groups.new_for_you", {n: Number(g.new_for_you)})) : null]),
    g.brief ? el("p", {class: "card__meta"}, g.brief) : null,
    el("div", {class: "avatar-stack"}, [...(g.members || []).map((m) => avatar(m.you ? (store.account()?.display_label || "you") : m.pseudonym, "avatar--small")), el("span", {class: "quiet"}, t("groups.members", {n: (g.members || []).length}))]),
    el("div", {class: "card__actions"}, [link(`/groups/${encodeURIComponent(g.workspace_id)}`, t("groups.open"), {class: "btn btn--small btn--primary"})])]))));
  return frag;
}

function newGroupForm() {
  const connections = store.connections();
  const g = ui.newGroup;
  const box = el("section", {class: "panel composer", "aria-label": t("groups.new")}, [el("h2", {class: "panel__title"}, t("groups.new"))]);
  box.append(el("label", {class: "field"}, [el("span", {class: "label"}, t("groups.new.with")), el("select", {onchange: (e) => { g.introId = e.target.value; }}, connections.map((c) => el("option", {value: c.intro_id, selected: c.intro_id === g.introId}, c.counterpart_display)))]));
  box.append(el("label", {class: "field"}, [el("span", {class: "label"}, t("groups.new.title")), el("input", {type: "text", maxLength: 200, value: g.title, oninput: (e) => { g.title = e.target.value; }})]));
  box.append(el("label", {class: "field"}, [el("span", {class: "label"}, t("groups.new.brief")), el("textarea", {rows: 3, maxLength: 2000, value: g.brief, oninput: (e) => { g.brief = e.target.value; }})]));
  box.append(el("div", {class: "row"}, [
    button(t("groups.new.create"), async () => {
      if (!g.title.trim() || !g.introId) return;
      const made = await attempt(() => store.write("/api/product/workspace/create", {request_id: store.requestId("ws"), confirmed: true, intro_id: g.introId, title: g.title.trim(), brief: g.brief.trim()}, {invalidate: {groups: true}}));
      if (made?.workspace_id) { ui.newGroup = null; await store.load(); navigate(`/groups/${encodeURIComponent(made.workspace_id)}`); }
    }, {variant: "btn--primary"}),
    button(t("cancel"), () => { ui.newGroup = null; render(); }, {variant: "btn--quiet"})]));
  return box;
}

function groupView() {
  const frag = document.createDocumentFragment();
  const id = current().param;
  if (store.getState().phase === "signed-out") { frag.append(landing(true)); return frag; }
  const entry = store.getState().groups.get(id);
  if (!entry) store.group(id);
  else if (store.groupIsStale(id)) store.group(id, {force: true});
  const listed = store.topics().topics.find((g) => g.workspace_id === id);
  frag.append(el("p", {class: "crumbs"}, link("/groups", `← ${t("group.back")}`)));
  if (!entry || (entry.loading && !entry.detail)) { frag.append(el("h1", {}, listed?.title || ""), el("div", {class: "skeleton"})); return frag; }
  if (entry.error && !entry.detail) { frag.append(el("p", {class: "status status--error"}, entry.error)); return frag; }
  const d = entry.detail;
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, d.title), d.brief ? el("p", {class: "lede"}, d.brief) : null,
    el("div", {class: "avatar-stack"}, [...d.members.map((m) => avatar(m.display, "avatar--small")), el("span", {class: "quiet"}, d.members.map((m) => m.display).join(", "))])]));
  const tabs = ["discussion", "parts", "understanding", "members"];
  frag.append(el("div", {class: "tabs", role: "tablist"}, tabs.map((tab) => el("button", {type: "button", role: "tab", class: "tab", "aria-selected": String(ui.groupTab === tab), onclick: () => { ui.groupTab = tab; render(); }}, t(`group.tab.${tab}`)))));
  const panel = el("section", {class: "tabpanel", role: "tabpanel"});
  if (ui.groupTab === "discussion") panel.append(discussionTab(d));
  else if (ui.groupTab === "parts") panel.append(partsTab(d));
  else if (ui.groupTab === "understanding") panel.append(understandingTab(d, entry.topic));
  else panel.append(membersTab(d));
  frag.append(panel);
  return frag;
}

function discussionTab(d) {
  const box = el("div", {});
  const list = el("ol", {class: "messages"});
  if (!d.notes.length) list.append(el("li", {class: "quiet"}, t("group.post.empty")));
  const me = store.account()?.display_label;
  for (const note of d.notes) list.append(el("li", {class: `message ${note.author_display === me ? "message--me" : ""}`}, [el("span", {class: "message__who"}, note.author_display), el("p", {class: "message__body"}, note.body), el("span", {class: "message__when"}, timeAgo(note.created_at))]));
  const area = draftField("textarea", `post-${d.workspace_id}`, {rows: 2, maxLength: 4000, placeholder: t("group.post.placeholder")});
  const send = button(t("group.post.send"), async () => {
    const body = area.value.trim();
    if (!body) return;
    send.disabled = true;
    const done = await attempt(() => store.write("/api/product/workspace/note", {workspace_id: d.workspace_id, body, confirmed: true, request_id: store.requestId("note")}, {invalidate: {group: d.workspace_id}}));
    send.disabled = false;
    if (done) { clearDraft(`post-${d.workspace_id}`); area.value = ""; store.group(d.workspace_id, {force: true}); }
  }, {variant: "btn--primary"});
  area.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send.click(); });
  box.append(list, el("div", {class: "compose-row"}, [area, send]));
  return box;
}

function partsTab(d) {
  const box = el("div", {}, [el("p", {class: "lede"}, t("group.parts.lede"))]);
  const list = el("ul", {class: "parts"});
  if (!d.tasks.length) list.append(el("li", {class: "quiet"}, t("group.parts.empty")));
  for (const task of d.tasks) {
    const setState = (state) => attempt(() => store.write("/api/product/workspace/task_state", {workspace_id: d.workspace_id, task_id: task.task_id, state, confirmed: true}, {invalidate: {group: d.workspace_id}})).then(() => store.group(d.workspace_id, {force: true}));
    const actions = el("div", {class: "row"});
    if (task.state === "todo") actions.append(button(t("group.parts.take"), () => setState("doing"), {variant: "btn--small btn--primary"}));
    if (task.state === "doing") actions.append(button(t("group.parts.finish"), () => setState("done"), {variant: "btn--small btn--primary"}));
    if (task.state === "done") actions.append(button(t("group.parts.reopen"), () => setState("todo"), {variant: "btn--small btn--quiet"}));
    list.append(el("li", {class: `part part--${task.state}`}, [el("span", {class: `chip chip--${task.state}`}, t(`group.parts.${task.state}`)), el("span", {class: "part__title"}, task.title), actions]));
  }
  const input = draftField("input", `part-${d.workspace_id}`, {type: "text", maxLength: 300, placeholder: t("group.parts.placeholder")});
  const add = button(t("group.parts.add"), async () => {
    const title = input.value.trim();
    if (!title) return;
    const done = await attempt(() => store.write("/api/product/workspace/task", {workspace_id: d.workspace_id, title, confirmed: true}, {invalidate: {group: d.workspace_id}}));
    if (done) { clearDraft(`part-${d.workspace_id}`); input.value = ""; store.group(d.workspace_id, {force: true}); }
  }, {variant: "btn--primary"});
  box.append(list, el("div", {class: "compose-row"}, [input, add]));
  return box;
}

function understandingTab(d, topic) {
  const box = el("div", {}, [el("p", {class: "lede"}, t("group.understanding.lede"))]);
  const standing = topic?.standing;
  const standBox = el("section", {class: "standing"}, [el("h3", {class: "section__title"}, t("group.understanding.standing"))]);
  if (!standing?.available) standBox.append(el("p", {class: "quiet"}, t("group.understanding.first")));
  else for (const side of standing.sides || []) {
    const part = el("div", {class: "side"}, [el("h4", {}, [t("group.understanding.with", {who: side.with_pseudonym}), " · ", verdict(side.classification)])]);
    const block = (label, rows, fmt) => rows.length ? el("div", {class: "side__block"}, [el("span", {class: "label"}, label), el("ul", {}, rows.map((r) => el("li", {}, fmt(r))))]) : null;
    part.append(block(t("group.understanding.agreed"), side.agreed_nodes || [], (r) => [r.yours, el("span", {class: "arrow"}, " ↔ "), r.theirs]),
      block(t("group.understanding.contested"), side.contested || [], (r) => [`${r.kind}: `, r.yours, el("span", {class: "arrow"}, " ✕ "), r.theirs]),
      block(t("group.understanding.yours_open"), side.yours_unanswered || [], (r) => r),
      block(t("group.understanding.theirs_open"), side.theirs_unanswered || [], (r) => r));
    standBox.append(part);
  }
  box.append(standBox);
  const contributions = el("section", {}, [el("h3", {class: "section__title"}, t("group.tab.understanding"))]);
  const delta = topic?.delta || [];
  if (!delta.length) contributions.append(el("p", {class: "quiet"}, t("group.understanding.empty")));
  for (const item of delta) contributions.append(el("article", {class: "contribution"}, [el("p", {class: "message__who"}, t("group.understanding.by", {who: item.author_pseudonym, when: timeAgo(item.created_at)})), item.note ? el("blockquote", {class: "their-words"}, item.note) : null, structure(item.thought?.nodes, item.thought?.relations)]));
  box.append(contributions, contributeForm(d));
  return box;
}

function contributeForm(d) {
  if (!ui.contribute || ui.contribute.workspace !== d.workspace_id) ui.contribute = {workspace: d.workspace_id, step: "write", text: "", note: "", preview: null, busy: false, error: ""};
  const c = ui.contribute;
  const box = el("section", {class: "panel composer"}, [el("h3", {class: "panel__title"}, t("group.understanding.add"))]);
  const status = el("p", {class: `status ${c.error ? "status--error" : ""}`, role: "status"}, c.busy ? t("thoughts.composer.reading") : c.error);
  if (c.step === "write") {
    const area = el("textarea", {rows: 4, maxLength: 4000, placeholder: t("group.understanding.placeholder"), value: c.text, oninput: (e) => { c.text = e.target.value; }});
    const mine = store.discoverableThoughts();
    box.append(area, el("div", {class: "row"}, [
      button(t("group.understanding.show"), async () => {
        if (!c.text.trim()) { area.focus(); return; }
        c.busy = true; c.error = ""; render();
        try {
          const got = await store.write("/api/product/topic/preview", {context: c.text});
          if (!got?.thought?.nodes?.length) throw new Error(t("thoughts.composer.nothing"));
          c.preview = got.thought; c.step = "preview";
        } catch (error) { c.error = error.message; }
        c.busy = false; render();
      }, {variant: "btn--primary", disabled: c.busy}),
      mine.length ? button(t("group.understanding.use_thought"), () => { c.preview = graphOf(mine[0]); c.step = "preview"; render(); }, {variant: "btn--quiet"}) : null]), status);
    return box;
  }
  const noteInput = el("input", {type: "text", maxLength: 1000, value: c.note, placeholder: t("group.understanding.note"), oninput: (e) => { c.note = e.target.value; }});
  box.append(structure(c.preview.nodes, c.preview.relations), noteInput, el("div", {class: "row"}, [
    button(t("group.understanding.submit"), async () => {
      c.busy = true; render();
      const done = await attempt(() => store.write("/api/product/topic/contribute", {request_id: store.requestId("contrib"), workspace_id: d.workspace_id, thought: {nodes: c.preview.nodes, relations: c.preview.relations}, note: c.note, confirmed: true, authorship: "their_own_words"}, {invalidate: {group: d.workspace_id}}));
      c.busy = false;
      if (done) { ui.contribute = null; store.group(d.workspace_id, {force: true}); } else render();
    }, {variant: "btn--primary", disabled: c.busy}),
    button(t("thoughts.composer.back"), () => { c.step = "write"; c.preview = null; render(); }, {variant: "btn--quiet"})]), status);
  return box;
}

function membersTab(d) {
  const box = el("div", {});
  box.append(el("ul", {class: "members"}, d.members.map((m) => el("li", {class: "member"}, [avatar(m.display), el("span", {}, m.display), el("span", {class: "quiet"}, m.state === "invited" ? t("group.role.invited") : t(`group.role.${m.role === "owner" ? "owner" : "member"}`))]))));
  const present = new Set(d.members.map((m) => m.display));
  const candidates = store.connections().filter((c) => !present.has(c.counterpart_display));
  const invite = el("section", {class: "panel"}, [el("h3", {class: "panel__title"}, t("group.invite"))]);
  if (!candidates.length) invite.append(el("p", {class: "quiet"}, t("group.invite.none")));
  else {
    const select = el("select", {}, candidates.map((c) => el("option", {value: c.intro_id}, c.counterpart_display)));
    invite.append(el("div", {class: "row"}, [select, button(t("group.invite.send"), async () => {
      const done = await attempt(() => store.write("/api/product/topic/invite", {workspace_id: d.workspace_id, intro_id: select.value, confirmed: true}, {invalidate: {group: d.workspace_id}}));
      if (done) store.group(d.workspace_id, {force: true});
    }, {variant: "btn--primary"})]));
  }
  box.append(invite);
  if (d.role !== "owner") box.append(el("p", {}, button(t("group.leave"), async () => {
    const done = await attempt(() => store.write("/api/product/workspace/leave", {workspace_id: d.workspace_id, confirmed: true}, {invalidate: {groups: true}}));
    if (done) navigate("/groups");
  }, {variant: "btn--quiet btn--small"})));
  return box;
}

// ---- connect --------------------------------------------------------------------------------------

function connectView() {
  const frag = document.createDocumentFragment();
  const url = `${window.location.origin}/mcp`;
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("connect.title")), el("p", {class: "lede"}, t("connect.lede"))]));
  frag.append(el("section", {class: "panel"}, [el("h2", {class: "panel__title"}, t("connect.address")),
    el("div", {class: "url-row"}, [el("code", {class: "url"}, url), button(t("connect.copy"), async () => { try { await navigator.clipboard.writeText(url); toast(t("copied")); } catch { toast(url); } }, {variant: "btn--small"})]),
    el("p", {class: "hint"}, t("connect.note")), el("p", {class: "hint"}, t("connect.same_account"))]));
  const tabs = ["claude", "chatgpt", "grok", "cli", "json", "browser"];
  frag.append(el("div", {class: "tabs", role: "tablist"}, tabs.map((tab) => el("button", {type: "button", role: "tab", class: "tab", "aria-selected": String(ui.connectTab === tab), onclick: () => { ui.connectTab = tab; render(); }}, t(`connect.tab.${tab}`)))));
  const panel = el("section", {class: "tabpanel", role: "tabpanel"});
  const tab = ui.connectTab;
  if (tab === "cli") panel.append(el("pre", {class: "code"}, `claude mcp add --transport http resonance ${url}`));
  else if (tab === "json") panel.append(el("p", {}, t("connect.steps.json")), el("pre", {class: "code"}, JSON.stringify({mcpServers: {resonance: {url}}}, null, 2)));
  else if (tab === "browser") {
    panel.append(el("p", {}, (document.modelContext || navigator.modelContext) ? t("connect.steps.browser.yes") : t("connect.steps.browser.no")));
    const status = document.getElementById("tool-status");
    if (status) { status.hidden = false; panel.append(status); }
  } else panel.append(el("p", {}, t(`connect.steps.${tab}`)));
  frag.append(panel);
  frag.append(el("section", {class: "panel"}, [el("h2", {class: "panel__title"}, t("connect.ask.title")), el("ul", {class: "asks"}, [1, 2, 3].map((n) => el("li", {}, el("em", {}, t(`connect.ask.${n}`))))), el("p", {class: "hint"}, t("connect.ask.note"))]));
  return frag;
}

// ---- render -----------------------------------------------------------------------------------------

let rendering = false;
let deferred = false;

function typing() {
  const active = document.activeElement;
  return !!active && active.closest?.("#view") && (active.tagName === "TEXTAREA" || active.tagName === "INPUT" || active.tagName === "SELECT");
}

// A render held back while the person was typing runs once focus leaves the
// field, but not at once: a click on a button starts with the field losing
// focus, and re-drawing the page between mousedown and mouseup would swallow
// the click. The pause is long enough for the click to land first.
document.addEventListener("focusout", () => { if (deferred) setTimeout(() => { if (deferred && !typing()) { deferred = false; render(); } }, 250); });

export function render() {
  if (rendering) return;
  if (typing()) { deferred = true; renderHeader(); return; }
  rendering = true;
  try {
    const s = store.getState();
    const main = document.getElementById("view");
    renderHeader();
    const route = current();
    document.title = route.nav === "home" ? "Resonance" : `${t(`nav.${route.nav}`)} · Resonance`;
    if (s.phase === "loading") { main.replaceChildren(el("div", {class: "skeleton-grid"}, [el("div", {class: "skeleton"}), el("div", {class: "skeleton"})])); return; }
    if (s.phase === "error") { main.replaceChildren(el("p", {class: "status status--error"}, t("error.generic", {message: s.error})), button(t("error.retry"), () => store.load())); return; }
    if (s.phase === "signed-out" && route.nav !== "home" && route.nav !== "connect") { history.replaceState({}, "", "/"); rendering = false; render(); return; }
    const status = document.getElementById("tool-status");
    if (status && route.nav !== "connect") { status.hidden = true; document.getElementById("tool-home")?.append(status); }
    main.replaceChildren(route.view());
    main.classList.remove("view--in"); void main.offsetWidth; main.classList.add("view--in");
    const footClaim = document.getElementById("foot-claim");
    if (footClaim) footClaim.textContent = t("footer.claim");
  } finally {
    rendering = false;
  }
}

function wireNotices() {
  const box = document.getElementById("notice");
  const toastNode = document.getElementById("toast");
  let toastTimer = null;
  document.addEventListener("resonance:notice", (event) => {
    const message = event.detail?.message || "";
    if (!message) { box.hidden = true; return; }
    box.replaceChildren(el("span", {}, message), button("×", () => { box.hidden = true; }, {variant: "btn--quiet btn--small"}));
    box.hidden = false;
  });
  document.addEventListener("resonance:toast", (event) => {
    toastNode.textContent = event.detail?.message || "";
    toastNode.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastNode.hidden = true; }, 2400);
  });
}

function boot() {
  const slot = document.getElementById("account-slot");
  if (slot?.dataset.accountLabel) store.getState().stamped = {display_label: slot.dataset.accountLabel, sign_in_email: slot.dataset.accountEmail || "", signed_in: slot.dataset.accountSignedIn === "true"};
  wireNotices();
  store.subscribe(() => render());
  render();
  store.load();
  store.startPolling();
  document.addEventListener("resonance:sign-in-required", () => { store.load(); });
}

if (typeof document !== "undefined") { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot(); }

export { el, structure, timeAgo, verdict, strengthWord };
