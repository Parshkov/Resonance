/**
 * The page: a router, a header, and one view per screen.
 *
 *   /            what is new, and how this works
 *   /thoughts    the thoughts you have here, and the place to share one
 *   /people      who resonates with a thought of yours, and why
 *   /talk        introductions and conversations
 *   /groups      groups around one idea; /groups/<id> is one of them
 *   /connect     the same product from the chat you already use
 *
 * Every view is a pure function of the store and a little local UI state.
 * Nothing here matches, ranks or rescores: every number shown is one the
 * engine returned, and every order is the engine's order.
 */

import * as store from "/store.mjs";
import { t } from "/strings.mjs";

// ---- tiny DOM helpers ---------------------------------------------------------

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
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function link(href, label, props = {}) {
  return el("a", {href, dataset: {link: "1"}, ...props}, label);
}

function button(label, onclick, {variant = "", type = "button", disabled = false} = {}) {
  return el("button", {type, class: `btn ${variant}`.trim(), onclick, disabled}, label);
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

// A thought's structure, the one way it is drawn everywhere on the page:
// the ideas as chips, then each link as a sentence.
function structure(nodes = [], relations = []) {
  const labels = new Map();
  for (const node of nodes) labels.set(node.id ?? node.label, node.label);
  const box = el("div", {class: "structure"});
  const ideas = el("ul", {class: "ideas"}, nodes.map((node) =>
    el("li", {class: "idea"}, [el("span", {class: "idea__label"}, node.label)])));
  const links = el("ul", {class: "links"}, relations.map((rel) => {
    const from = rel.from ?? labels.get(rel.source) ?? rel.source;
    const to = rel.to ?? labels.get(rel.target) ?? rel.target;
    return el("li", {class: "link-row"}, [
      el("span", {}, from), el("span", {class: "link-type"}, relationWord(rel.type)), el("span", {}, to)]);
  }));
  box.append(ideas, links);
  return box;
}

function notice(message) {
  document.dispatchEvent(new CustomEvent("resonance:notice", {detail: {message}}));
}

function toast(message) {
  document.dispatchEvent(new CustomEvent("resonance:toast", {detail: {message}}));
}

async function attempt(action) {
  try { return await action(); } catch (error) { notice(t("error.generic", {message: error.message})); return null; }
}

function stateChip(stateWord) {
  return el("span", {class: `chip chip--${stateWord}`}, t(`thoughts.state.${stateWord}`));
}

function empty(title, body) {
  return el("div", {class: "empty"}, [el("p", {class: "empty__title"}, title), body ? el("p", {class: "empty__body"}, body) : null]);
}

// ---- router -------------------------------------------------------------------

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

// ---- local UI state (per screen) --------------------------------------------

const ui = {
  composer: null,            // {step, text, preview, busy}
  stopAsk: null,             // session_id awaiting a yes/no
  peopleThought: null,
  peopleSelected: null,
  askOpen: null,             // session_id whose intro composer is open
  askSent: new Set(),
  talkThread: null,          // {channel_id, messages, loading}
  talkPoll: null,
  groupTab: "discussion",
  newGroup: null,            // {introId, title, brief}
  contribute: null,          // {text, note, preview, busy}
  drafts: {},                // field id -> what is typed, kept across re-renders
};

// A text field the page rebuilds on every render must not lose what was typed:
// the poll, or any write elsewhere, re-renders the screen. What is typed lives
// in ui.drafts under the field's id until it is sent.
function draftField(tag, id, props = {}) {
  const node = el(tag, {...props, id, value: ui.drafts[id] || ""});
  node.addEventListener("input", () => { ui.drafts[id] = node.value; });
  return node;
}

function clearDraft(id) { delete ui.drafts[id]; }

// ---- header ---------------------------------------------------------------------

function counts() {
  const s = store.getState();
  const unseen = store.alerts().filter((a) => !a.seen_at).length;
  const {incoming} = store.intros();
  const requests = incoming.filter((r) => r.state === "requested").length;
  const {topics, invitations} = store.topics();
  const groupsNew = invitations.length + topics.reduce((sum, g) => sum + (Number(g.new_for_you) || 0), 0);
  return {home: unseen + requests + invitations.length, people: unseen, talk: requests, groups: groupsNew, ready: s.phase === "ready"};
}

function renderHeader() {
  const nav = document.getElementById("page-nav");
  const route = current();
  const badge = counts();
  const signedOut = store.getState().phase === "signed-out";
  // Signed out, the product has no screens to show: the page is the
  // introduction, and the one other place to go is how to connect a chat.
  const items = signedOut ? [["connect", "/connect"]]
    : [["home", "/"], ["thoughts", "/thoughts"], ["people", "/people"], ["talk", "/talk"], ["groups", "/groups"], ["connect", "/connect"]];
  nav.replaceChildren(...items.map(([key, href]) => {
    const a = link(href, [t(`nav.${key}`), badge[key] ? el("span", {class: "nav-badge", "aria-label": t("nav.new")}, String(badge[key])) : null],
      {class: "nav-link"});
    if (route.nav === key) a.setAttribute("aria-current", "page");
    return a;
  }));
  renderAccount();
}

function renderAccount() {
  const slot = document.getElementById("account-slot");
  const s = store.getState();
  const account = store.account();
  slot.replaceChildren();
  if (s.phase === "signed-out" || !account?.display_label) {
    const signIn = el("a", {class: "btn btn--primary btn--small", href: signInHref()}, t("account.signin"));
    slot.append(signIn, settingsMenu(null));
    return;
  }
  slot.append(settingsMenu(account));
}

function signInHref() {
  const base = store.getState().overview?.sign_in_url || "/auth/sign-in";
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  return `${base}?next=${next}`;
}

function settingsMenu(account) {
  const wrap = el("div", {class: "menu"});
  const label = account ? account.display_label : "Aa";
  const initials = account ? label.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase() : "";
  const trigger = el("button", {type: "button", class: "menu__button", "aria-haspopup": "true", "aria-expanded": "false", "aria-label": t("account.menu")},
    account ? [el("span", {class: "avatar"}, initials), el("span", {class: "menu__name"}, label)] : [el("span", {class: "avatar avatar--quiet"}, "Aa")]);
  const panel = el("div", {class: "menu__panel", hidden: true});
  if (account) {
    panel.append(el("p", {class: "menu__caption"}, t("account.seen_as")), el("p", {class: "menu__value"}, label),
      el("p", {class: "menu__note"}, t("account.pseudonym_note")));
    if (account.signed_in && account.sign_in_email) {
      panel.append(el("p", {class: "menu__caption"}, t("account.signed_in_as")), el("p", {class: "menu__value"}, account.sign_in_email),
        el("p", {class: "menu__note"}, t("account.only_you")));
    } else if (account.signed_in === false) {
      panel.append(el("p", {class: "menu__note"}, t("account.browser_only")));
    }
  }
  // colours
  const theme = window.__resonanceTheme;
  const choice = theme?.choice?.() || document.documentElement.getAttribute("data-theme-choice") || "light";
  const themeRow = el("div", {class: "menu__row"}, [el("span", {class: "menu__caption"}, t("account.colours")),
    el("div", {class: "segmented", role: "radiogroup"}, ["light", "dark", "system"].map((value) =>
      el("label", {class: "segmented__option"}, [
        el("input", {type: "radio", name: "theme", value, checked: value === choice,
          onchange: () => { if (theme?.choose) theme.choose(value); else document.documentElement.setAttribute("data-theme", value === "dark" ? "dark" : "light"); }}),
        el("span", {}, t(`account.theme.${value}`))])))]);
  panel.append(themeRow);
  if (account && account.signed_in) {
    const form = el("form", {method: "post", action: "/auth/sign-out", class: "menu__out"});
    form.append(el("button", {type: "submit", class: "btn btn--small"}, t("account.signout")));
    panel.append(form);
  }
  trigger.addEventListener("click", () => {
    const open = panel.hidden;
    panel.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) { panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); }
  });
  wrap.append(trigger, panel);
  return wrap;
}

// ---- home -------------------------------------------------------------------------

function homeView() {
  const s = store.getState();
  const frag = document.createDocumentFragment();
  const signedOut = s.phase === "signed-out";
  const mine = store.thoughts();
  if (signedOut || mine.length === 0) {
    frag.append(intro(signedOut));
    if (signedOut) return frag;
  }
  if (mine.length) frag.append(newsSection(), summary());
  return frag;
}

function intro(signedOut) {
  const hero = el("section", {class: "hero"}, [
    el("h1", {class: "hero__title"}, t("home.title")),
    el("p", {class: "hero__lede"}, t("home.lede")),
    el("p", {class: "hero__lede"}, t("home.then")),
  ]);
  const steps = el("ol", {class: "steps"}, [1, 2, 3].map((n) => el("li", {class: "step"}, [
    el("span", {class: "step__n"}, String(n)),
    el("h2", {class: "step__title"}, t(`home.step${n}.title`)),
    el("p", {class: "step__body"}, t(`home.step${n}.body`))])));
  const actions = el("div", {class: "hero__actions"});
  if (signedOut) {
    actions.append(el("a", {class: "btn btn--primary", href: signInHref()}, t("home.cta.signin")),
      el("p", {class: "hero__why"}, t("home.signin_why")));
  } else {
    actions.append(link("/thoughts", t("home.cta.share"), {class: "btn btn--primary"}));
  }
  actions.append(link("/connect", t("home.cta.connect"), {class: "btn btn--quiet"}));
  hero.append(actions);
  const wrap = el("div", {class: "landing"}, [hero, steps]);
  return wrap;
}

function summary() {
  const mine = store.thoughts();
  const discoverable = mine.filter((r) => r.state === "discoverable").length;
  const people = store.alerts().length;
  const talks = store.connections().length;
  const groups = store.topics().topics.length;
  const tile = (href, big, small) => link(href, [el("span", {class: "tile__big"}, big), small ? el("span", {class: "tile__small"}, small) : null], {class: "tile"});
  return el("section", {class: "tiles", "aria-label": t("home.whats_new")}, [
    tile("/thoughts", t("home.summary.thoughts", {n: mine.length}), t("home.summary.discoverable", {n: discoverable})),
    tile("/people", t("home.summary.people", {n: people}), ""),
    tile("/talk", t("home.summary.talks", {n: talks}), ""),
    tile("/groups", t("home.summary.groups", {n: groups}), ""),
  ]);
}

function topicOf(sessionId) {
  return store.thoughts().find((r) => r.session_id === sessionId)?.topic || "";
}

function newsSection() {
  const section = el("section", {class: "news"}, [el("h2", {class: "section__title"}, t("home.whats_new"))]);
  const items = [];
  for (const alert of store.alerts().filter((a) => !a.seen_at)) {
    const who = alert.person_pseudonym || "Someone";
    const text = alert.reason === "they_arrived"
      ? t("home.news.arrived", {who, topic: topicOf(alert.my_session_id)})
      : t("home.news.existing", {who, topic: topicOf(alert.my_session_id)});
    const about = alert.display?.topic ? el("p", {class: "news__meta"}, `“${alert.display.topic}”`) : null;
    const meta = [alert.display?.domain ? t("home.news.in", {domain: alert.display.domain}) : null,
      t("home.news.match", {score: score(alert.scores_at_detection?.structural)}), timeAgo(alert.detected_at)].filter(Boolean).join(" · ");
    items.push(el("li", {class: "news__item"}, [
      el("p", {class: "news__text"}, text), about, el("p", {class: "news__meta"}, meta),
      el("div", {class: "news__actions"}, [
        link(`/people?thought=${encodeURIComponent(alert.my_session_id)}&select=${encodeURIComponent(alert.their_session_id)}`, t("home.news.see"), {class: "btn btn--small btn--primary",
          onclick: () => { store.write("/api/product/resonances/seen", {alert_keys: [alert.alert_key]}); }}),
        button(t("home.news.dismiss"), () => attempt(() => store.write("/api/product/resonances/dismiss", {alert_key: alert.alert_key})), {variant: "btn--small btn--quiet"}),
      ])]));
  }
  for (const row of store.intros().incoming.filter((r) => r.state === "requested")) {
    items.push(el("li", {class: "news__item"}, [
      el("p", {class: "news__text"}, t("home.news.request", {who: row.counterpart_display})),
      el("p", {class: "news__meta"}, timeAgo(row.created_at)),
      el("div", {class: "news__actions"}, [link("/talk", t("home.news.answer"), {class: "btn btn--small btn--primary"})])]));
  }
  for (const inv of store.topics().invitations) {
    items.push(el("li", {class: "news__item"}, [
      el("p", {class: "news__text"}, t("home.news.invite", {who: inv.invited_by_pseudonym || "…", title: inv.title})),
      el("div", {class: "news__actions"}, [link("/groups", t("home.news.answer"), {class: "btn btn--small btn--primary"})])]));
  }
  for (const g of store.topics().topics.filter((g) => Number(g.new_for_you) > 0)) {
    items.push(el("li", {class: "news__item"}, [
      el("p", {class: "news__text"}, t("home.news.group_new", {n: Number(g.new_for_you), title: g.title})),
      el("div", {class: "news__actions"}, [link(`/groups/${encodeURIComponent(g.workspace_id)}`, t("home.news.open"), {class: "btn btn--small btn--primary"})])]));
  }
  section.append(items.length ? el("ul", {class: "news__list"}, items) : el("p", {class: "quiet"}, t("home.quiet")));
  return section;
}

// ---- thoughts ---------------------------------------------------------------------

function thoughtsView() {
  const frag = document.createDocumentFragment();
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("thoughts.title")), el("p", {class: "lede"}, t("thoughts.lede"))]));
  frag.append(composer());
  const mine = store.thoughts();
  if (!mine.length) { if (!ui.composer) frag.append(empty(t("thoughts.empty"))); return frag; }
  frag.append(el("ul", {class: "cards"}, mine.map(thoughtCard)));
  return frag;
}

// A draft is named by the server the moment it is shared. Until then the
// page names it the same way: the first idea and the last one.
function thoughtTitle(row) {
  const topic = String(row.topic || "").trim();
  if (topic && topic !== "Shared thought") return topic;
  const nodes = row.nodes || [];
  if (!nodes.length) return t("thoughts.structure");
  const last = row.relations?.length ? row.relations[row.relations.length - 1].to : nodes[nodes.length - 1].label;
  return last && last !== nodes[0].label ? `${nodes[0].label} → ${last}` : nodes[0].label;
}

function thoughtCard(row) {
  const when = row.state === "discoverable" ? t("thoughts.shared_at", {when: timeAgo(row.shared_at)})
    : row.state === "withdrawn" ? t("thoughts.withdrawn_at", {when: timeAgo(row.withdrawn_at)})
    : t("thoughts.prepared_at", {when: timeAgo(row.prepared_at)});
  const card = el("li", {class: "card thought"}, [
    el("div", {class: "card__head"}, [stateChip(row.state), el("span", {class: "card__when"}, when)]),
    el("h2", {class: "card__title"}, thoughtTitle(row)),
    el("p", {class: "card__meta"}, [row.domain ? `${t("thoughts.field")}: ${row.domain} · ` : "",
      t("thoughts.ideas", {n: row.nodes?.length || 0}), " · ", t("thoughts.links", {n: row.relations?.length || 0})]),
    el("p", {class: "hint"}, t(`thoughts.state.${row.state}.hint`)),
    el("details", {class: "disclosure"}, [el("summary", {}, t("thoughts.structure")), structure(row.nodes, row.relations)]),
  ]);
  const actions = el("div", {class: "card__actions"});
  if (row.state === "discoverable") {
    actions.append(link(`/people?thought=${encodeURIComponent(row.session_id)}`, t("thoughts.people"), {class: "btn btn--small btn--primary"}));
    if (ui.stopAsk === row.session_id) {
      actions.append(el("div", {class: "confirm"}, [el("p", {}, t("thoughts.stop.confirm")),
        button(t("thoughts.stop.yes"), async () => {
          ui.stopAsk = null;
          await attempt(() => store.write("/api/product/revoke", {session_id: row.session_id, request_id: store.requestId("stop"), confirmed: true}, {invalidate: {discovery: true}}));
        }, {variant: "btn--small btn--danger"}),
        button(t("thoughts.stop.no"), () => { ui.stopAsk = null; render(); }, {variant: "btn--small btn--quiet"})]));
    } else {
      actions.append(button(t("thoughts.stop"), () => { ui.stopAsk = row.session_id; render(); }, {variant: "btn--small btn--quiet"}));
    }
  }
  card.append(actions);
  return card;
}

function composer() {
  if (!ui.composer) {
    return el("div", {class: "composer-offer"}, [button(t("thoughts.new"), () => { ui.composer = {step: "write", text: "", preview: null, busy: false}; render(); }, {variant: "btn--primary"})]);
  }
  const c = ui.composer;
  const box = el("section", {class: "panel composer", "aria-label": t("thoughts.new")});
  if (c.step === "write") {
    const area = el("textarea", {id: "compose-text", rows: 6, maxLength: 4000, placeholder: t("thoughts.composer.placeholder"), value: c.text,
      oninput: (e) => { c.text = e.target.value; }});
    const status = el("p", {class: "status", role: "status"}, c.busy ? t("thoughts.composer.reading") : (c.error || ""));
    if (c.error) status.classList.add("status--error");
    const submit = button(t("thoughts.composer.extract"), async () => {
      if (!c.text.trim()) { area.focus(); return; }
      c.busy = true; c.error = ""; render();
      try {
        await store.write("/api/webmcp/prepare", {request_id: store.requestId("prep"), context: c.text, authorship: "their_own_words"});
        const preview = await fetch("/api/webmcp/preview", {credentials: "same-origin", cache: "no-store"}).then((r) => r.json());
        if (!preview?.confirmation_token) throw new Error(preview?.message || t("thoughts.composer.nothing"));
        c.preview = preview; c.step = "preview";
      } catch (error) {
        c.error = error.message;
      }
      c.busy = false; render();
    }, {variant: "btn--primary", disabled: c.busy});
    box.append(el("label", {for: "compose-text", class: "label"}, t("thoughts.composer.label")), area,
      el("p", {class: "hint"}, t("thoughts.composer.hint")),
      el("div", {class: "row"}, [submit, button(t("thoughts.composer.cancel"), () => { ui.composer = null; render(); }, {variant: "btn--quiet"})]), status);
    return box;
  }
  const p = c.preview;
  const shown = p.will_become_discoverable?.thought || {};
  const nodes = shown.nodes || [];
  const relations = shown.relations || [];
  const status = el("p", {class: "status", role: "status"}, c.error || "");
  if (c.error) status.classList.add("status--error");
  box.append(el("h2", {class: "panel__title"}, t("thoughts.composer.preview")), structure(nodes, relations),
    el("div", {class: "row"}, [
      button(t("thoughts.composer.share"), async () => {
        c.busy = true; render();
        try {
          await store.write("/api/webmcp/share", {request_id: store.requestId("share"), confirm: true, confirmation_token: p.confirmation_token}, {invalidate: {discovery: true}});
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

// ---- people --------------------------------------------------------------------------

function peopleView() {
  const frag = document.createDocumentFragment();
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("people.title")), el("p", {class: "lede"}, t("people.lede"))]));
  const shared = store.discoverableThoughts();
  if (!shared.length) {
    frag.append(empty(t("people.none_shared")), el("p", {}, link("/thoughts", t("thoughts.new"), {class: "btn btn--primary"})));
    return frag;
  }
  const route = current();
  const asked = route.query.get("thought");
  const chosen = shared.find((r) => r.session_id === (asked || ui.peopleThought)) || shared[0];
  ui.peopleThought = chosen.session_id;
  if (shared.length > 1) {
    frag.append(el("div", {class: "picker"}, [el("span", {class: "label"}, t("people.for")),
      el("select", {onchange: (e) => navigate(`/people?thought=${encodeURIComponent(e.target.value)}`)},
        shared.map((r) => el("option", {value: r.session_id, selected: r.session_id === chosen.session_id}, thoughtTitle(r))))]));
  } else {
    frag.append(el("p", {class: "picker"}, [el("span", {class: "label"}, t("people.for")), " ", el("strong", {}, thoughtTitle(chosen))]));
  }
  const entry = store.getState().discovery.get(chosen.session_id);
  if (!entry) { store.discover(chosen.session_id); }
  if (!entry || (entry.loading && !entry.payload)) { frag.append(el("p", {class: "quiet"}, t("loading"))); return frag; }
  if (entry.error && !entry.payload) {
    frag.append(el("p", {class: "status status--error"}, entry.error), button(t("error.retry"), () => store.discover(chosen.session_id, {force: true})));
    return frag;
  }
  const payload = entry.payload;
  const visible = (payload.matches || []).filter((m) => m.display?.share_state === "discoverable" && !m.hard_rejection);
  const people = visible.filter((m) => m.mode_classification !== "negative");
  const near = [...visible.filter((m) => m.mode_classification === "negative"),
    ...(payload.rejected || []).filter((m) => m.display?.share_state === "discoverable")];
  const wanted = route.query.get("select");
  if (wanted && people.some((m) => m.session_id === wanted)) ui.peopleSelected = wanted;
  if (!people.some((m) => m.session_id === ui.peopleSelected)) ui.peopleSelected = people[0]?.session_id || null;

  if (!people.length) {
    frag.append(empty(t("people.empty.title"), t("people.empty.body")));
  } else {
    const list = el("ol", {class: "match-list"}, people.map((m) => matchCard(m, chosen)));
    const detail = el("aside", {class: "detail"}, evidencePanel(people.find((m) => m.session_id === ui.peopleSelected), chosen));
    frag.append(el("p", {class: "count"}, t("people.found", {n: people.length})), el("div", {class: "split"}, [list, detail]));
  }
  if (payload.shape_note) frag.append(el("p", {class: "hint"}, payload.shape_note));
  if (near.length) {
    frag.append(el("details", {class: "disclosure near"}, [el("summary", {}, [t("people.near", {n: near.length}), " ", el("span", {class: "quiet"}, t("people.near.hint"))]),
      el("ul", {class: "near__list"}, near.map((m) => el("li", {}, [el("strong", {}, m.person_pseudonym), " · ", m.display?.topic || "", " · ",
        el("span", {class: "quiet"}, m.hard_rejection ? rejectionWords(m.hard_rejection) : verdict(m.mode_classification))])))]));
  }
  return frag;
}

function rejectionWords(reason) {
  const kind = String(reason || "").split(":")[0];
  if (kind === "direction") return t("people.reject.direction");
  if (kind === "relation_type") return t("people.reject.relation_type");
  return t("people.reject.other");
}

function matchCard(m) {
  const selected = m.session_id === ui.peopleSelected;
  const first = m.evidence?.top_correspondences?.[0];
  const card = el("li", {class: `match ${selected ? "is-selected" : ""}`});
  const open = el("button", {type: "button", class: "match__open", "aria-pressed": String(selected), onclick: () => { ui.peopleSelected = m.session_id; render(); }}, [
    el("div", {class: "match__top"}, [el("span", {class: "match__person"}, m.person_pseudonym), m.display?.domain ? el("span", {class: "match__domain"}, m.display.domain) : null]),
    el("p", {class: "match__topic"}, m.display?.topic || ""),
    el("p", {class: "match__verdict"}, verdict(m.mode_classification)),
    first ? el("p", {class: "match__why"}, [first.query_label, el("span", {class: "arrow"}, " ↔ "), first.candidate_label]) : null,
    el("div", {class: "strength"}, [el("progress", {max: 1, value: Math.max(0, Math.min(1, Number(m.scores?.structural) || 0)), "aria-hidden": "true"}),
      el("span", {}, strengthWord(m.scores?.structural)), el("span", {class: "quiet"}, score(m.scores?.structural))]),
    m.display?.demo_persona ? el("p", {class: "quiet"}, t("people.example")) : null,
  ]);
  card.append(open);
  return card;
}

function evidencePanel(m, thought) {
  if (!m) return el("p", {class: "quiet"}, t("people.select"));
  const box = el("div", {class: "evidence"});
  box.append(el("p", {class: "eyebrow"}, t("people.why")), el("h2", {class: "evidence__title"}, [m.person_pseudonym, " · ", m.display?.topic || ""]),
    el("p", {class: "evidence__verdict"}, [verdict(m.mode_classification), " · ", t(`people.confidence.${m.confidence || "medium"}`)]),
    el("p", {class: "evidence__score"}, [t("people.strength"), ": ", el("strong", {}, score(m.scores?.structural)), " · ",
      t("people.kept", {n: m.evidence?.preserved_relation_count || 0}),
      (m.evidence?.contradiction_count || 0) > 0 ? [" · ", t("people.contradictions", {n: m.evidence.contradiction_count})] : null]));
  const rows = el("div", {class: "mapping"}, [el("div", {class: "mapping__head"}, [el("span", {}, t("people.yours")), el("span", {}), el("span", {}, t("people.theirs"))])]);
  for (const pair of m.evidence?.top_correspondences || []) {
    rows.append(el("div", {class: "mapping__row"}, [el("span", {}, pair.query_label), el("span", {class: "arrow"}, "↔"), el("span", {}, pair.candidate_label)]));
  }
  box.append(el("p", {class: "label"}, t("people.correspond")), rows);
  box.append(introAction(m, thought));
  return box;
}

function introAction(m, thought) {
  const wrap = el("div", {class: "evidence__actions"});
  if (m.display?.demo_persona) return wrap;
  const existing = store.introFor(m.session_id);
  if (existing?.state === "accepted") {
    wrap.append(el("span", {class: "chip chip--ok"}, t("people.connected")), link(`/talk/${encodeURIComponent(existing.intro_id)}`, t("people.open_talk"), {class: "btn btn--small btn--primary"}));
    return wrap;
  }
  if (existing?.state === "requested" || ui.askSent.has(m.session_id)) { wrap.append(el("span", {class: "chip"}, t("people.asked"))); return wrap; }
  if (existing?.state === "declined") { wrap.append(el("span", {class: "chip chip--muted"}, t("people.declined"))); return wrap; }
  if (ui.askOpen !== m.session_id) {
    wrap.append(button(t("people.ask"), () => { ui.askOpen = m.session_id; render(); }, {variant: "btn--primary"}));
    return wrap;
  }
  const area = draftField("textarea", "ask-text", {rows: 4, maxLength: 500, placeholder: t("people.ask.placeholder")});
  const status = el("p", {class: "status", role: "status"});
  wrap.append(el("label", {for: "ask-text", class: "label"}, t("people.ask.label", {who: m.person_pseudonym})), area,
    el("div", {class: "row"}, [
      button(t("people.ask.send"), async () => {
        const message = area.value.trim();
        if (!message) { area.focus(); return; }
        const done = await attempt(() => store.write("/api/product/intro/request", {request_id: store.requestId("intro"), confirmed: true,
          from_session_id: thought.session_id, target_session_id: m.session_id, message}));
        if (done) { clearDraft("ask-text"); ui.askSent.add(m.session_id); ui.askOpen = null; toast(t("people.ask.sent")); render(); }
      }, {variant: "btn--primary"}),
      button(t("thoughts.composer.cancel"), () => { ui.askOpen = null; render(); }, {variant: "btn--quiet"})]), status);
  return wrap;
}

// ---- talk -----------------------------------------------------------------------------

function talkView() {
  const frag = document.createDocumentFragment();
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("talk.title")), el("p", {class: "lede"}, t("talk.lede"))]));
  const {incoming, outgoing} = store.intros();
  const pending = [...incoming.filter((r) => r.state === "requested"), ...outgoing.filter((r) => r.state === "requested")];
  if (pending.length) {
    frag.append(el("section", {class: "requests"}, [el("h2", {class: "section__title"}, t("talk.requests")),
      el("ul", {class: "cards"}, pending.map(requestCard))]));
  }
  const connections = store.connections();
  const route = current();
  const selectedId = route.param || (connections[0]?.intro_id ?? null);
  const selected = connections.find((c) => c.intro_id === selectedId) || null;
  if (!connections.length) { frag.append(empty(t("talk.empty"))); return frag; }
  const list = el("ul", {class: "convo-list"}, connections.map((c) => el("li", {}, link(`/talk/${encodeURIComponent(c.intro_id)}`,
    [el("span", {class: "convo__who"}, c.counterpart_display), el("span", {class: "convo__when"}, timeAgo(c.updated_at))],
    {class: `convo ${selected?.intro_id === c.intro_id ? "is-selected" : ""}`}))));
  const thread = selected ? threadPanel(selected) : el("p", {class: "quiet"}, t("talk.pick"));
  frag.append(el("div", {class: "split split--talk"}, [el("aside", {}, [el("h2", {class: "section__title"}, t("talk.list")), list]), el("section", {class: "thread"}, thread)]));
  return frag;
}

function requestCard(row) {
  const incoming = row.direction === "incoming";
  const card = el("li", {class: "card request"}, [
    el("p", {class: "card__title"}, incoming ? t("talk.incoming", {who: row.counterpart_display}) : t("talk.outgoing", {who: row.counterpart_display})),
    el("blockquote", {class: "their-words"}, row.message), el("p", {class: "card__when"}, timeAgo(row.created_at))]);
  const actions = el("div", {class: "card__actions"});
  if (incoming) {
    actions.append(button(t("talk.accept"), () => attempt(() => store.write("/api/product/intro/respond", {intro_id: row.intro_id, accept: true, confirmed: true, request_id: store.requestId("acc")})), {variant: "btn--small btn--primary"}),
      button(t("talk.decline"), () => attempt(() => store.write("/api/product/intro/respond", {intro_id: row.intro_id, accept: false, confirmed: true, request_id: store.requestId("dec")})), {variant: "btn--small btn--quiet"}));
  } else {
    actions.append(el("span", {class: "chip"}, t("talk.waiting")),
      button(t("talk.cancel"), () => attempt(() => store.write("/api/product/intro/cancel", {intro_id: row.intro_id, confirmed: true, request_id: store.requestId("can")})), {variant: "btn--small btn--quiet"}));
  }
  card.append(actions);
  return card;
}

function threadPanel(intro) {
  const box = el("div", {class: "thread__box"});
  const thread = ui.talkThread;
  if (!thread || thread.channel_id !== intro.channel_id) {
    ui.talkThread = {channel_id: intro.channel_id, messages: null, loading: true};
    loadThread(intro.channel_id);
  }
  const messages = ui.talkThread?.messages;
  box.append(el("header", {class: "thread__head"}, [el("h2", {class: "section__title"}, intro.counterpart_display), el("p", {class: "quiet"}, t("talk.relay"))]));
  const list = el("ol", {class: "messages"});
  if (messages === null || messages === undefined) list.append(el("li", {class: "quiet"}, t("loading")));
  else if (!messages.length) list.append(el("li", {class: "quiet"}, t("talk.nothing_yet")));
  else for (const m of messages) {
    list.append(el("li", {class: `message ${m.author === "me" ? "message--me" : ""}`}, [
      el("span", {class: "message__who"}, m.author === "me" ? t("talk.you") : m.author_display), el("p", {class: "message__body"}, m.body), el("span", {class: "message__when"}, timeAgo(m.created_at))]));
  }
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
  box.append(el("p", {class: "quiet"}, link("/groups", t("talk.open_group", {who: intro.counterpart_display}),
    {onclick: () => { ui.newGroup = {introId: intro.intro_id, title: "", brief: ""}; }})));
  return box;
}

async function loadThread(channelId) {
  try {
    const payload = await store.messages(channelId);
    if (ui.talkThread?.channel_id === channelId) { ui.talkThread.messages = payload.messages || []; ui.talkThread.loading = false; render(); }
  } catch (error) {
    // A read that failed must not leave "Loading…" on the screen for good:
    // say so, and show the empty thread, which the next poll will fill.
    if (ui.talkThread?.channel_id === channelId) { ui.talkThread.messages = []; ui.talkThread.loading = false; render(); }
    notice(t("error.generic", {message: error.message}));
  }
}

// ---- groups -------------------------------------------------------------------------

function groupsView() {
  const frag = document.createDocumentFragment();
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("groups.title")), el("p", {class: "lede"}, t("groups.lede"))]));
  const {topics, invitations} = store.topics();
  if (invitations.length) {
    frag.append(el("section", {}, [el("h2", {class: "section__title"}, t("groups.invitations")), el("ul", {class: "cards"}, invitations.map((inv) =>
      el("li", {class: "card"}, [el("p", {class: "card__title"}, t("groups.invite.line", {who: inv.invited_by_pseudonym || "…", title: inv.title})),
        el("div", {class: "card__actions"}, [
          button(t("groups.invite.join"), () => attempt(() => store.write("/api/product/workspace/respond", {workspace_id: inv.workspace_id, accept: true, confirmed: true}, {invalidate: {groups: true}})), {variant: "btn--small btn--primary"}),
          button(t("groups.invite.later"), () => attempt(() => store.write("/api/product/workspace/respond", {workspace_id: inv.workspace_id, accept: false, confirmed: true})), {variant: "btn--small btn--quiet"})])])))]));
  }
  frag.append(newGroupForm());
  if (!topics.length) { frag.append(empty(t("groups.empty"))); return frag; }
  frag.append(el("ul", {class: "cards"}, topics.map((g) => el("li", {class: "card group-card"}, [
    el("div", {class: "card__head"}, [el("h2", {class: "card__title"}, link(`/groups/${encodeURIComponent(g.workspace_id)}`, g.title)),
      Number(g.new_for_you) > 0 ? el("span", {class: "chip chip--new"}, t("groups.new_for_you", {n: Number(g.new_for_you)})) : null]),
    g.brief ? el("p", {class: "card__meta"}, g.brief) : null,
    el("p", {class: "quiet"}, [t("groups.members", {n: (g.members || []).length}), ": ", (g.members || []).map((m) => m.you ? t("group.you") : m.pseudonym).join(", ")]),
    el("div", {class: "card__actions"}, [link(`/groups/${encodeURIComponent(g.workspace_id)}`, t("groups.open"), {class: "btn btn--small btn--primary"})])]))));
  return frag;
}

function newGroupForm() {
  const connections = store.connections();
  if (!ui.newGroup) {
    return el("div", {class: "composer-offer"}, [button(t("groups.new"), () => { ui.newGroup = {introId: connections[0]?.intro_id || "", title: "", brief: ""}; render(); }, {variant: "btn--primary", disabled: !connections.length}),
      !connections.length ? el("p", {class: "hint"}, t("groups.new.none")) : null]);
  }
  const g = ui.newGroup;
  const box = el("section", {class: "panel composer", "aria-label": t("groups.new")});
  box.append(el("h2", {class: "panel__title"}, t("groups.new")));
  box.append(el("label", {class: "label", for: "ng-with"}, t("groups.new.with")),
    el("select", {id: "ng-with", onchange: (e) => { g.introId = e.target.value; }}, connections.map((c) => el("option", {value: c.intro_id, selected: c.intro_id === g.introId}, c.counterpart_display))));
  box.append(el("label", {class: "label", for: "ng-title"}, t("groups.new.title")), el("input", {id: "ng-title", type: "text", maxLength: 200, value: g.title, oninput: (e) => { g.title = e.target.value; }}));
  box.append(el("label", {class: "label", for: "ng-brief"}, t("groups.new.brief")), el("textarea", {id: "ng-brief", rows: 3, maxLength: 2000, value: g.brief, oninput: (e) => { g.brief = e.target.value; }}));
  box.append(el("div", {class: "row"}, [
    button(t("groups.new.create"), async () => {
      if (!g.title.trim() || !g.introId) return;
      const made = await attempt(() => store.write("/api/product/workspace/create", {request_id: store.requestId("ws"), confirmed: true, intro_id: g.introId, title: g.title.trim(), brief: g.brief.trim()}, {invalidate: {groups: true}}));
      if (made?.workspace_id) { ui.newGroup = null; await store.load(); navigate(`/groups/${encodeURIComponent(made.workspace_id)}`); }
    }, {variant: "btn--primary"}),
    button(t("thoughts.composer.cancel"), () => { ui.newGroup = null; render(); }, {variant: "btn--quiet"})]));
  return box;
}

function groupView() {
  const frag = document.createDocumentFragment();
  const id = current().param;
  const entry = store.getState().groups.get(id);
  if (!entry) store.group(id);
  else if (store.groupIsStale(id)) store.group(id, {force: true});
  const listed = store.topics().topics.find((g) => g.workspace_id === id);
  frag.append(el("p", {class: "crumbs"}, link("/groups", `← ${t("group.back")}`)));
  if (!entry || (entry.loading && !entry.detail)) { frag.append(el("h1", {}, listed?.title || ""), el("p", {class: "quiet"}, t("loading"))); return frag; }
  if (entry.error && !entry.detail) { frag.append(el("p", {class: "status status--error"}, entry.error)); return frag; }
  const d = entry.detail;
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, d.title), d.brief ? el("p", {class: "lede"}, d.brief) : null,
    el("p", {class: "quiet"}, [t("groups.members", {n: d.members.length}), ": ", d.members.map((m) => m.display).join(", ")])]));
  const tabs = ["discussion", "parts", "understanding", "members"];
  const tablist = el("div", {class: "tabs", role: "tablist"}, tabs.map((tab) => el("button", {type: "button", role: "tab", class: "tab", "aria-selected": String(ui.groupTab === tab),
    onclick: () => { ui.groupTab = tab; render(); }}, t(`group.tab.${tab}`))));
  frag.append(tablist);
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
  for (const note of d.notes) {
    list.append(el("li", {class: "message"}, [el("span", {class: "message__who"}, note.author_display), el("p", {class: "message__body"}, note.body), el("span", {class: "message__when"}, timeAgo(note.created_at))]));
  }
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
  // where the group stands
  const standing = topic?.standing;
  const standBox = el("section", {class: "standing"}, [el("h3", {class: "section__title"}, t("group.understanding.standing"))]);
  if (!standing?.available) standBox.append(el("p", {class: "quiet"}, standing?.reason ? t("group.understanding.first") : t("group.understanding.first")));
  else for (const side of standing.sides || []) {
    const part = el("div", {class: "side"}, [el("h4", {}, [t("group.understanding.with", {who: side.with_pseudonym}), " · ", verdict(side.classification)])]);
    const block = (label, rows, fmt) => rows.length ? el("div", {class: "side__block"}, [el("span", {class: "label"}, label), el("ul", {}, rows.map((r) => el("li", {}, fmt(r))))]) : null;
    for (const piece of [
      block(t("group.understanding.agreed"), side.agreed_nodes || [], (r) => [r.yours, el("span", {class: "arrow"}, " ↔ "), r.theirs]),
      block(t("group.understanding.contested"), side.contested || [], (r) => [`${r.kind}: `, r.yours, el("span", {class: "arrow"}, " ✕ "), r.theirs]),
      block(t("group.understanding.yours_open"), side.yours_unanswered || [], (r) => r),
      block(t("group.understanding.theirs_open"), side.theirs_unanswered || [], (r) => r),
    ]) if (piece) part.append(piece);
    standBox.append(part);
  }
  box.append(standBox);
  // contributions
  const contributions = el("section", {}, [el("h3", {class: "section__title"}, t("group.tab.understanding"))]);
  const delta = topic?.delta || [];
  if (!delta.length && !(topic?.contributions_total > 0)) contributions.append(el("p", {class: "quiet"}, t("group.understanding.empty")));
  for (const item of delta) {
    contributions.append(el("article", {class: "contribution"}, [el("p", {class: "message__who"}, t("group.understanding.by", {who: item.author_pseudonym, when: timeAgo(item.created_at)})),
      item.note ? el("blockquote", {class: "their-words"}, item.note) : null, structure(item.thought?.nodes, item.thought?.relations)]));
  }
  box.append(contributions);
  box.append(contributeForm(d));
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
    const row = el("div", {class: "row"}, [
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
      mine.length ? button(t("group.understanding.use_thought"), () => {
        const first = mine[0];
        c.preview = {nodes: first.nodes.map((n, i) => ({id: `n${i}`, label: n.label, role: n.role})),
          relations: first.relations.map((r) => ({source: `n${first.nodes.findIndex((n) => n.label === r.from)}`, target: `n${first.nodes.findIndex((n) => n.label === r.to)}`, type: r.type}))};
        c.step = "preview"; render();
      }, {variant: "btn--quiet"}) : null]);
    box.append(area, row, status);
    return box;
  }
  const noteInput = el("input", {type: "text", maxLength: 1000, value: c.note, placeholder: t("group.understanding.note"), oninput: (e) => { c.note = e.target.value; }});
  box.append(structure(c.preview.nodes, c.preview.relations), noteInput, el("div", {class: "row"}, [
    button(t("group.understanding.submit"), async () => {
      c.busy = true; render();
      const done = await attempt(() => store.write("/api/product/topic/contribute", {request_id: store.requestId("contrib"), workspace_id: d.workspace_id, thought: c.preview, note: c.note, confirmed: true, authorship: "their_own_words"}, {invalidate: {group: d.workspace_id}}));
      c.busy = false;
      if (done) { ui.contribute = null; store.group(d.workspace_id, {force: true}); } else render();
    }, {variant: "btn--primary", disabled: c.busy}),
    button(t("thoughts.composer.back"), () => { c.step = "write"; c.preview = null; render(); }, {variant: "btn--quiet"})]), status);
  return box;
}

function membersTab(d) {
  const box = el("div", {});
  box.append(el("ul", {class: "members"}, d.members.map((m) => el("li", {class: "member"}, [el("span", {class: "avatar"}, m.display.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase()),
    el("span", {}, m.display), el("span", {class: "quiet"}, m.state === "invited" ? t("group.role.invited") : t(`group.role.${m.role === "owner" ? "owner" : "member"}`))]))));
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
  if (d.role !== "owner") {
    box.append(el("p", {}, button(t("group.leave"), async () => {
      const done = await attempt(() => store.write("/api/product/workspace/leave", {workspace_id: d.workspace_id, confirmed: true}, {invalidate: {groups: true}}));
      if (done) navigate("/groups");
    }, {variant: "btn--quiet btn--small"})));
  }
  return box;
}

// ---- connect --------------------------------------------------------------------------

function connectView() {
  const frag = document.createDocumentFragment();
  const url = `${window.location.origin}/mcp`;
  frag.append(el("header", {class: "page-head"}, [el("h1", {}, t("connect.title")), el("p", {class: "lede"}, t("connect.lede"))]));
  const address = el("section", {class: "panel"}, [el("h2", {class: "panel__title"}, t("connect.address")),
    el("div", {class: "url-row"}, [el("code", {class: "url"}, url), button(t("connect.copy"), async () => {
      try { await navigator.clipboard.writeText(url); toast(t("copied")); } catch { toast(url); }
    }, {variant: "btn--small"})]),
    el("p", {class: "hint"}, t("connect.note")), el("p", {class: "hint"}, t("connect.same_account"))]);
  frag.append(address);
  const tabs = ["claude", "chatgpt", "grok", "cli", "json", "browser"];
  ui.connectTab = ui.connectTab || "claude";
  const tablist = el("div", {class: "tabs", role: "tablist"}, tabs.map((tab) => el("button", {type: "button", role: "tab", class: "tab", "aria-selected": String(ui.connectTab === tab), onclick: () => { ui.connectTab = tab; render(); }}, t(`connect.tab.${tab}`))));
  const panel = el("section", {class: "tabpanel", role: "tabpanel"});
  const tab = ui.connectTab;
  if (tab === "cli") panel.append(el("pre", {class: "code"}, `claude mcp add --transport http resonance ${url}`));
  else if (tab === "json") panel.append(el("p", {}, t("connect.steps.json")), el("pre", {class: "code"}, JSON.stringify({mcpServers: {resonance: {url}}}, null, 2)));
  else if (tab === "browser") {
    const has = !!(document.modelContext || navigator.modelContext);
    panel.append(el("p", {}, has ? t("connect.steps.browser.yes") : t("connect.steps.browser.no")));
    const status = document.getElementById("tool-status");
    if (status) { status.hidden = false; panel.append(status); }
  } else panel.append(el("p", {}, t(`connect.steps.${tab}`)));
  frag.append(tablist, panel);
  frag.append(el("section", {class: "panel"}, [el("h2", {class: "panel__title"}, t("connect.ask.title")),
    el("ul", {class: "asks"}, [1, 2, 3].map((n) => el("li", {}, el("em", {}, t(`connect.ask.${n}`))))), el("p", {class: "hint"}, t("connect.ask.note"))]));
  return frag;
}

// ---- render ----------------------------------------------------------------------------

let rendering = false;
let deferred = false;

function typing() {
  const active = document.activeElement;
  return !!active && active.closest?.("#view") && (active.tagName === "TEXTAREA" || active.tagName === "INPUT" || active.tagName === "SELECT");
}

document.addEventListener("focusout", () => {
  if (deferred && !typing()) { deferred = false; setTimeout(() => render(), 0); }
});

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
    if (s.phase === "loading") {
      main.replaceChildren(el("p", {class: "quiet loading"}, t("loading")));
      return;
    }
    if (s.phase === "error") {
      main.replaceChildren(el("p", {class: "status status--error"}, t("error.generic", {message: s.error})), button(t("error.retry"), () => store.load()));
      return;
    }
    if (s.phase === "signed-out" && route.nav !== "home" && route.nav !== "connect") {
      history.replaceState({}, "", "/");
      rendering = false;
      render();
      return;
    }
    // the WebMCP status pill lives with the Connect page; keep it out of the way elsewhere
    const status = document.getElementById("tool-status");
    if (status && route.nav !== "connect") { status.hidden = true; document.getElementById("tool-home")?.append(status); }
    main.replaceChildren(route.view());
    const footClaim = document.getElementById("foot-claim");
    if (footClaim) footClaim.textContent = t("footer.claim");
    for (const [id, key] of [["foot-privacy", "footer.privacy"], ["foot-terms", "footer.terms"], ["foot-support", "footer.support"]]) {
      const node = document.getElementById(id);
      if (node) node.textContent = t(key);
    }
  } finally {
    rendering = false;
  }
}

// ---- notices -----------------------------------------------------------------------------

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

// ---- boot --------------------------------------------------------------------------------

function boot() {
  const slot = document.getElementById("account-slot");
  if (slot?.dataset.accountLabel) {
    store.getState().stamped = {display_label: slot.dataset.accountLabel, sign_in_email: slot.dataset.accountEmail || "", signed_in: slot.dataset.accountSignedIn === "true"};
  }
  wireNotices();
  store.subscribe(() => render());
  render();
  store.load();
  store.startPolling();
  document.addEventListener("resonance:sign-in-required", () => { store.load(); });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
}

export { el, structure, timeAgo, verdict, strengthWord };
