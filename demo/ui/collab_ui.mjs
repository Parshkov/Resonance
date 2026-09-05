/**
 * Contacting a person: the human UI for steps 4 and 5 of the product's loop.
 *
 * Share a thought → people are found → you ask one of them for an
 * introduction → they accept or decline → a private channel opens. This
 * module renders the share control, the "ask for an introduction" action on
 * every match card, the requests inbox and the message thread. Every control
 * drives the same /api/product endpoints the WebMCP tools use, so manual UI
 * and agent produce identical authorized state.
 *
 * It used to be a right-hand drawer opened from a "Collaboration" button in
 * the masthead. Finding people is pointless if reaching them is hidden behind
 * an overlay, so the same surfaces now render into sections of the page:
 *   #share-state / #share-composer / #share-control
 *                                        — what is discoverable, the composer
 *                                          while nothing is, stop sharing once
 *                                          something is
 *   .match-card .match-card__actions    — ask for an introduction
 *   #collab-initiate                     — people open to one, without a card
 *   #collab-requests, #collab-channel    — the Conversations section
 *   #connect-advanced                    — the developer key, behind the URL
 * Presentation comes from /live_ui.css (CSP `default-src 'self'`). The
 * module re-reads its state after every successful write made through
 * session.mjs (agent tools included) and polls slowly for requests and
 * messages from other people.
 *
 * All returned intro/message text is user-generated: it is inserted via
 * textContent (never innerHTML), so it is displayed, never interpreted, and
 * it is visibly marked as somebody else's words.
 */

import { apiFetch } from "/session.mjs";

let requestCounter = 0;
let refreshTimer = null;
let pollTimer = null;

// What the last reads said. Cards and alerts render from these without a
// request of their own.
const state = {
  introStates: new Map(),      // session_id -> {intro_state, person_pseudonym, demo_persona}
  requests: {incoming: [], outgoing: []},
  querySession: null,
  openChannelId: null,
  openCounterpart: "",
};

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of [].concat(children)) {
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function byId(id) { return document.getElementById(id); }

// A request id names one intent, so that a retry of the same write (session.mjs
// retries after a rotated CSRF token) is answered once and not done twice.
// It used to be the counter plus a slice of the CSRF token -- and the counter
// starts again at 1 on every page load while the token is kept across loads.
// So after a reload, the first "Stop sharing" sent the same id as the one
// before the reload, and the server answered with that earlier, already
// committed result: nothing was withdrawn, and the page said so. Found by
// pressing it. A nonce made once per load keeps retries within a load
// idempotent and makes every load's writes its own.
const loadNonce = Math.random().toString(36).slice(2, 10);
function requestId(prefix) {
  requestCounter += 1;
  return `ui-${prefix}-${requestCounter}-${loadNonce}`;
}

// Anything that went wrong is said once, in the page's one notice slot
// (shell.mjs), whichever surface it came from. Signed-out is not an error
// here: the account module already shows the way in.
function showError(message) {
  if (message && /^Sign in to Resonance/.test(message)) return;
  document.dispatchEvent(new CustomEvent("resonance:notice", {detail: {message: message || ""}}));
}

function actionButton(label, handler, variant = "") {
  const className = variant === "primary" ? "collab-button collab-button--primary"
    : variant === "quiet" ? "collab-button collab-button--quiet" : "collab-button";
  const button = el("button", {type: "button", textContent: label, className});
  button.addEventListener("click", async () => {
    button.disabled = true;
    showError("");
    try { await handler(); } catch (error) { showError(error.message); }
    button.disabled = false;
  });
  return button;
}

function relativeTime(iso) {
  const then = Date.parse(iso || "");
  if (!Number.isFinite(then)) return "";
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.floor(minutes)} min ago`;
  const hours = minutes / 60;
  if (hours < 48) return `${Math.floor(hours)} h ago`;
  const days = hours / 24;
  if (days < 14) return `${Math.floor(days)} d ago`;
  return new Date(then).toLocaleDateString();
}

// Text someone else wrote: shown as text, marked as theirs.
function theirWords(text, from) {
  const node = el("p", {className: "their-words", textContent: text || ""});
  if (from) node.dataset.from = from;
  return node;
}

// ---- share state (human path for prepare → preview → confirm → share) ----
//
// The same three steps an agent takes over MCP, done by hand on the page:
// the person's own words go in (never retained), the structure that would
// become discoverable is shown back, and nothing is shared until they say so
// having seen it. A prepare with no content is refused by the server — there
// is no stand-in thought — so the page has to ask for the words first.

const SHARE_PLACEHOLDER =
  "What are you working on, and what is hard about it? Say what causes what, what " +
  "prevents what, what requires what — the structure comes from those words.\n\n" +
  "For example: “A partial outage causes synchronized client retries. The retries cause " +
  "request amplification, which leads to cascading saturation. Jittered backoff prevents " +
  "the amplification.”";

const SHARE_TRUST =
  "Your words are not kept. Only the structure — what causes what — is compared, " +
  "and you will see exactly that before anyone else can.";

function humanRelation(type) {
  return String(type || "").replace(/_/g, " ");
}

// This is all anyone will ever see: the nodes and the typed relations.
function previewStructure(preview) {
  const thought = preview?.will_become_discoverable?.thought || {};
  const presentation = preview?.will_become_discoverable?.presentation || {};
  const nodes = Array.isArray(thought.nodes) ? thought.nodes : [];
  const relations = Array.isArray(thought.relations) ? thought.relations : [];
  const labelOf = new Map(nodes.map((n) => [n.id, n.label]));
  const box = el("section", {className: "share-preview"});
  box.setAttribute("aria-label", "What would become visible");
  box.append(el("h3", {className: "share-preview__title", textContent: "This is all anyone will ever see"}));
  if (presentation.topic && presentation.topic !== "Shared thought") {
    box.append(el("p", {className: "share-preview__topic", textContent: presentation.topic}));
  }
  const chain = el("ol", {className: "dna-chain"});
  chain.setAttribute("aria-label", "Nodes");
  for (const node of nodes) {
    const row = el("li", {className: "dna-node"});
    row.append(el("strong", {textContent: node.label || ""}), el("span", {textContent: node.role || ""}));
    chain.append(row);
  }
  box.append(chain);
  const list = el("ol", {className: "dna-relations"});
  list.setAttribute("aria-label", "Relations");
  for (const relation of relations) {
    const row = el("li", {className: "dna-relation"});
    row.append(
      el("span", {textContent: labelOf.get(relation.source) || relation.source || ""}),
      el("span", {className: "relation-type", textContent: humanRelation(relation.type)}),
      el("span", {textContent: labelOf.get(relation.target) || relation.target || ""}),
    );
    list.append(row);
  }
  box.append(list);
  box.append(el("p", {className: "share-preview__note", textContent:
    "Your text itself is not kept. Only these nodes and relations are compared, and only " +
    "the people they resonate with can see them — under your pseudonym, with no way to reach you " +
    "until you both agree."}));
  return box;
}

// The exposure moment. The textarea is on the page as soon as there is
// nothing shared — it is the page's one action — and the promise that makes
// it bearable sits next to it, not in a paragraph somewhere else.
function openShareComposer() {
  const host = byId("share-composer");
  if (!host) return;
  if (host.querySelector(".share-form")) return;
  const form = el("form", {className: "share-form"});
  const id = "share-context";
  form.append(el("label", {htmlFor: id, className: "visually-hidden", textContent: "Your thought, in your own words"}));
  const textarea = el("textarea", {id, name: "context", required: true, maxLength: 4000,
    placeholder: SHARE_PLACEHOLDER, rows: 6});
  const status = el("p", {className: "share-form__status", role: "status"});
  const row = el("div", {className: "share-form__row"});
  const extract = el("button", {type: "submit", className: "collab-button collab-button--primary",
    textContent: "Show me what would be shared"});
  row.append(extract, el("p", {className: "share-form__trust", textContent: SHARE_TRUST}));
  form.append(textarea, row, status);
  host.replaceChildren(form);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const context = textarea.value.trim();
    if (!context) { textarea.focus(); return; }
    extract.disabled = true;
    status.classList.remove("is-error");
    status.textContent = "Reading the structure…";
    let preview;
    try {
      // This is the person, typing into their own page. The authorship
      // question exists because an assistant driving these tools might be
      // sharing its own framing under someone's name; here there is no
      // assistant between the words and the person who wrote them, and the
      // page can say so truthfully rather than asking them to confirm what
      // they just did.
      await apiFetch("POST", "/api/webmcp/prepare", {
        request_id: requestId("prep"), context,
        authorship: "their_own_words",
      });
      preview = await apiFetch("GET", "/api/webmcp/preview");
    } catch (error) {
      status.classList.add("is-error");
      status.textContent = error.message;
      extract.disabled = false;
      return;
    }
    status.textContent = "";
    // Step 2: the preview, and the explicit share. Nothing is discoverable yet.
    const confirmRow = el("div", {className: "share-form__row"});
    const share = el("button", {type: "button", className: "collab-button collab-button--primary",
      textContent: "Share this and start looking"});
    const back = el("button", {type: "button", className: "collab-button collab-button--quiet",
      textContent: "Change the text"});
    const previewBox = previewStructure(preview);
    share.addEventListener("click", async () => {
      share.disabled = true;
      try {
        await apiFetch("POST", "/api/webmcp/share", {
          request_id: requestId("share"), confirm: true,
          confirmation_token: preview.confirmation_token,
        });
        host.replaceChildren();
        await refreshAll();
        byId("people")?.scrollIntoView({block: "start"});
      } catch (error) {
        status.classList.add("is-error");
        status.textContent = error.message;
        share.disabled = false;
      }
    });
    back.addEventListener("click", () => {
      previewBox.remove(); confirmRow.remove();
      textarea.hidden = false; row.hidden = false; extract.disabled = false;
      textarea.focus();
    });
    confirmRow.append(share, back, el("p", {className: "share-form__trust", textContent:
      "Nothing is visible until you press share, and you can stop at any moment."}));
    textarea.hidden = true; row.hidden = true;
    form.append(previewBox, confirmRow, status);
    previewBox.setAttribute("tabindex", "-1");
    previewBox.focus({preventScroll: false});
  });
}

async function stopSharing() {
  await apiFetch("POST", "/api/webmcp/consent", {
    request_id: requestId("revoke"), shared: false, confirm: true,
  });
}

// What pressing "Yes, stop" will do, in the person's situation. The control
// sits beside the one thought the panel shows and stops that one; when they
// have others out there, saying so is the difference between "I stopped
// sharing" and "I stopped sharing this".
export function stopSharingMeans(counts) {
  const others = Math.max(0, (counts?.discoverable || 0) - 1);
  const sentence = "This thought leaves discovery now and stops looking. Anyone it matched stops seeing it.";
  if (others === 0) return sentence;
  return `${sentence} Your ${others === 1 ? "other thought stays" : `${others} other thoughts stay`} discoverable.`;
}

// Stop sharing asks once, inline, where the person can read what it means.
function stopSharingControl(host, counts) {
  const stop = el("button", {type: "button", className: "collab-button", textContent: "Stop sharing"});
  stop.addEventListener("click", () => {
    const box = el("div", {className: "stop-confirm", role: "group"});
    box.setAttribute("aria-label", "Confirm stop sharing");
    // The question is answered once it is done: the box goes before the
    // re-read, because the re-read leaves a box alone (someone may be mid-
    // question) and this one would otherwise stay on screen beside whichever
    // thought the panel shows next -- with a "Yes, stop" that now means that
    // one.
    const yes = actionButton("Yes, stop", async () => {
      await stopSharing();
      box.remove();
      await refreshAll();
    }, "primary");
    const keep = el("button", {type: "button", className: "collab-button collab-button--quiet", textContent: "Keep sharing"});
    keep.addEventListener("click", () => { box.replaceWith(stop); stop.focus(); });
    box.append(el("p", {textContent: stopSharingMeans(counts)}), yes, keep);
    stop.replaceWith(box);
    yes.focus();
  });
  host.append(stop);
}

// The one line about the person, from the three counts the server reports
// (the same three the chat's whoami reports, sorted by the same function).
//
// It used to read "Private · nothing of yours is discoverable" whenever
// nothing was -- to someone whose only thought was withdrawn, whose thought
// is not private, it is withdrawn. Withdrawn is not private, and private is
// not shared: three facts, three clauses, each true of the thing it names.
// "Nothing of yours is discoverable" is a claim about the person and is only
// ever made when it is true of the person.
export function shareStateWords(counts) {
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const discoverable = counts?.discoverable || 0;
  const withdrawn = counts?.withdrawn || 0;
  const kept = counts?.private || 0;
  const parts = [discoverable > 0
    ? `Discoverable · ${n(discoverable, "thought", "thoughts")} · still looking`
    : "Nothing of yours is discoverable"];
  if (withdrawn > 0) parts.push(`${n(withdrawn, "thought", "thoughts")} withdrawn`);
  if (kept > 0) parts.push(`${n(kept, "thought", "thoughts")} kept private here`);
  return parts.join(" · ");
}

// One line, in one place, says what is discoverable. The control beside it
// is the one thing that changes that.
function renderShareState(counts) {
  const shared = (counts?.discoverable || 0) > 0;
  const line = byId("share-state");
  if (line) {
    const light = el("span", {className: "status-light"});
    light.setAttribute("aria-hidden", "true");
    line.replaceChildren(light, shareStateWords(counts));
    line.dataset.shared = String(shared);
  }
  const control = byId("share-control");
  if (!control) return;
  if (control.querySelector(".stop-confirm")) return;   // mid-question: leave it
  control.replaceChildren();
  if (shared) stopSharingControl(control, counts);
}

// The person's own sessions, as the intro roster needs them (consent choices
// included). The share line used to be derived from the same rows; it now
// reads the three counts from /api/product/mine instead, see refreshShare.
async function ownedSessions() {
  return (await apiFetch("GET", "/api/product/sessions")).sessions || [];
}

// The share line is about the person: how many of their thoughts are
// discoverable, withdrawn, kept private. /api/product/mine sorts them into
// those three states with the very function the chat's whoami uses, so this
// reads that rather than restating the rule over the raw rows -- the two
// halves have disagreed about these words before, and a rule in two places
// is how. One read of the person's own record, not a discovery.
async function refreshShare() {
  let mine;
  try {
    mine = await apiFetch("GET", "/api/product/mine");
  } catch (error) {
    showError(error.message);
    return;
  }
  const counts = mine.counts || {};
  const shared = (counts.discoverable || 0) > 0;
  // Same announcement webmcp_live.mjs makes, for the human path: sharing from
  // this page must also take it out of its onboarding state. This one also
  // says WHICH thoughts are discoverable, so the page can tell "one of two
  // withdrawn" from "nothing changed"; those identifiers are for comparing
  // and never reach the screen.
  const discoverable = (mine.thoughts || [])
    .filter((t) => t.state === "discoverable").map((t) => t.session_id);
  document.dispatchEvent(new CustomEvent("resonance:consent", {detail: {shared, discoverable}}));
  renderShareState(counts);
  // Nothing shared: the composer IS the page's action, so it is open. Once
  // something is shared the panel shows the thought instead.
  if (shared) byId("share-composer")?.replaceChildren();
  else openShareComposer();
}

// ---- connect: the developer fallback, after the URL that is the real path --

function codeBlock(text) {
  const pre = el("pre", {className: "collab-code"});
  pre.textContent = text; // key material and commands: text only
  return pre;
}

function renderConnect() {
  const host = byId("connect-advanced");
  if (!host) return;
  // The page's connect panel leads with the one address a client needs
  // ("Hand your client this one address": the URL, OAuth discovered by the
  // client itself). This module only adds the developer fallback behind a
  // disclosure, after it. This panel used to lead with "Create MCP key" and
  // hand out `Authorization: Bearer <key>`; ops/CONNECT_MCP.md §2 calls that
  // "debug only, not the normal path", and submission/HUMAN_TEST_CARDS.md
  // tells a tester that being asked for a key is a FAIL.
  const endpoint = `${window.location.origin}/mcp`;
  host.replaceChildren(
    el("details", {className: "collab-advanced"}, [
      el("summary", {textContent: "Advanced: mint a key (debug only)"}),
      el("p", {className: "collab-muted", textContent:
        "Only for a client that cannot run OAuth at all. A key is a second login for this " +
        "account: anyone holding it acts as you. Prefer the URL above. You will not be asked to paste a " +
        "key anywhere in the normal flow."}),
      el("div", {className: "collab-compose-inline"}, [
        actionButton("Create MCP key", async () => {
          const creds = await apiFetch("POST", "/api/product/mcp_key", {});
          const url = creds.endpoint || endpoint;
          const out = byId("collab-connect-out");
          out.replaceChildren(
            el("p", {className: "collab-muted", textContent:
              "Shown once — anyone holding this key acts as you in Resonance. " +
              `Expires ${creds.expires_at}.`}),
            codeBlock(`claude mcp add --transport http resonance ${url} \\\n  --header "Authorization: Bearer ${creds.mcp_key}"`),
            codeBlock(JSON.stringify({mcpServers: {resonance: {url,
              headers: {Authorization: `Bearer ${creds.mcp_key}`}}}}, null, 2)),
          );
        }),
      ]),
      el("div", {id: "collab-connect-out"}),
    ]),
  );
}

// ---- the introduction composer -----------------------------------------
//
// One inline form, used by the match cards, the roster and the waiting
// resonances. It replaces a browser prompt dialog: the person sees what they are
// sending, to whom, and what the other side will and will not receive.

function introComposer({fromSessionId, targetSessionId, who, onSent, onCancel}) {
  const form = el("form", {className: "intro-composer"});
  const id = `intro-message-${targetSessionId.replace(/[^A-Za-z0-9_-]/g, "")}`;
  const label = el("label", {htmlFor: id, textContent:
    `A short message to ${who || "them"}. They see it with your pseudonym, nothing else.`});
  const textarea = el("textarea", {id, name: "message", required: true, maxLength: 500,
    placeholder: "What made you want to talk — and what you are working on."});
  const row = el("div", {className: "intro-composer-row"});
  const send = el("button", {type: "submit", className: "collab-button collab-button--primary",
    textContent: "Send the request"});
  const cancel = el("button", {type: "button", className: "collab-button collab-button--quiet",
    textContent: "Cancel"});
  cancel.addEventListener("click", () => { form.remove(); onCancel?.(); });
  row.append(send, cancel, el("p", {className: "collab-muted", textContent:
    "Nothing opens until they accept."}));
  form.append(label, textarea, row);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = textarea.value.trim();
    if (!message) { textarea.focus(); return; }
    send.disabled = true;
    showError("");
    try {
      await requestIntro(fromSessionId, targetSessionId, message);
      form.remove();
      await onSent?.();
    } catch (error) {
      showError(error.message);
      send.disabled = false;
    }
  });
  queueMicrotask(() => textarea.focus());
  return form;
}

// ---- intro initiation -------------------------------------------------

function introStateFor(sessionId) {
  return state.introStates.get(sessionId) || null;
}

function acceptedIntroFor(sessionId) {
  // Outgoing rows name the target session; incoming ones deliberately do not
  // name the other person's session, so a card can only find its own request.
  return [...state.requests.outgoing, ...state.requests.incoming].find((row) =>
    row.state === "accepted" && row.channel_id && row.to_session_id === sessionId) || null;
}

// The action that belongs on a person, wherever they are shown: a card, a
// roster row, or an alert. Reads the latest authorized state and never offers
// what the backend would refuse (a seeded example cannot accept).
function actionsFor(sessionId, host, options = {}) {
  host.replaceChildren();
  const info = introStateFor(sessionId);
  // An alert names the thought of yours that resonated; a card uses the
  // discoverable thought the page is showing.
  const fromSession = options.fromSessionId || state.querySession;
  const who = options.who || info?.person_pseudonym || "";
  if (options.demoPersona || info?.demo_persona) {
    host.append(el("span", {className: "collab-muted", textContent:
      "An example from the seeded corpus — not a person who can be introduced."}));
    return;
  }
  if (!fromSession) {
    host.append(el("span", {className: "collab-muted", textContent: "Share a thought to ask for an introduction."}));
    return;
  }
  const connection = options.connectionState || info?.intro_state || null;
  if (connection === "accepted") {
    const row = acceptedIntroFor(sessionId);
    host.append(el("span", {className: "collab-state", textContent: "connected"}));
    host.querySelector(".collab-state").dataset.state = "accepted";
    host.append(actionButton("Open conversation", async () => {
      if (row) await openChannel(row);
      else byId("conversations")?.scrollIntoView({block: "start"});
    }, "primary"));
    return;
  }
  if (connection === "requested") {
    // The state has no direction. Outgoing rows name their target session;
    // if none of ours points at this person, the open request is theirs.
    const ours = state.requests.outgoing.some((row) =>
      row.state === "requested" && row.to_session_id === sessionId);
    const badge = el("span", {className: "collab-state", textContent:
      ours ? "introduction requested" : "they asked you"});
    badge.dataset.state = "requested";
    host.append(badge);
    if (ours) {
      host.append(el("span", {className: "collab-muted", textContent: "Waiting for them to answer."}));
    } else {
      const answer = el("a", {href: "#conversations", className: "collab-muted", textContent:
        "They asked to be introduced to you — answer below."});
      host.append(answer);
    }
    return;
  }
  if (connection === "unavailable") {
    host.append(el("span", {className: "collab-muted", textContent: "Not taking introductions right now."}));
    return;
  }
  const ask = el("button", {type: "button", textContent: "Ask for an introduction",
    className: "collab-button collab-button--primary collab-request-btn"});
  ask.addEventListener("click", (event) => {
    event.stopPropagation();
    if (host.querySelector(".intro-composer")) return;
    ask.hidden = true;
    host.append(introComposer({
      fromSessionId: fromSession, targetSessionId: sessionId, who,
      onSent: async () => { await refreshAll(); },
      onCancel: () => { ask.hidden = false; },
    }));
  });
  host.append(ask);
}

async function refreshInitiate(owned) {
  // People open to an introduction, from the same authorized discovery the
  // page shows. Cards on the page get their action from this read; anyone
  // available who has no card is listed here so they can still be reached.
  const host = byId("collab-initiate");
  try {
    owned = owned || await ownedSessions();
  } catch (error) {
    showError(error.message);
    return;
  }
  const mine = owned.find((s) => s.share_state === "discoverable") || null;
  state.introStates = new Map();
  host?.replaceChildren();
  if (!mine) {
    state.querySession = null;
    delete document.body.dataset.querySession;
    return;
  }
  state.querySession = mine.session_id;
  document.body.dataset.querySession = mine.session_id;
  let matches = [];
  try {
    matches = (await apiFetch(
      "GET", `/api/product/rich_discover?session_id=${encodeURIComponent(mine.session_id)}&k=8`)).matches || [];
  } catch (error) {
    showError(error.message);
    return;
  }
  for (const match of matches) {
    state.introStates.set(match.session_id, {
      intro_state: match.intro_state,
      person_pseudonym: match.person_pseudonym,
      demo_persona: match.display?.demo_persona === true,
    });
  }
  if (!host) return;
  const onPage = new Set([...document.querySelectorAll(".match-card[data-session-id]")]
    .map((card) => card.dataset.sessionId));
  const reachable = matches.filter((m) =>
    m.intro_state === "available" && m.display?.demo_persona !== true && !onPage.has(m.session_id));
  if (!reachable.length) return;
  host.append(el("h4", {className: "collab-subhead", textContent: "Also open to an introduction"}));
  for (const match of reachable) {
    const row = el("div", {className: "collab-row collab-initiate-row"});
    row.dataset.sessionId = match.session_id;
    // person_pseudonym and topic are untrusted UGC -> textContent.
    row.append(el("span", {className: "collab-grow"}, [
      el("strong", {textContent: match.person_pseudonym}),
      match.display?.topic ? ` · ${match.display.topic}` : "",
    ]));
    const actions = el("div", {className: "match-card__actions"});
    actionsFor(match.session_id, actions, {who: match.person_pseudonym});
    row.append(actions);
    host.append(row);
  }
}

// ---- requests -----------------------------------------------------------

function setBadge(count) {
  // The navigation (shell.mjs) reads the count off the section itself.
  const section = byId("conversations");
  if (section) {
    if (count > 0) section.dataset.navCount = String(count);
    else delete section.dataset.navCount;
  }
  const line = byId("news-requests");
  if (line) {
    line.replaceChildren();
    if (count > 0) {
      const link = el("a", {href: "#conversations", textContent: "Answer below"});
      line.append(count === 1 ? "Someone asked to be introduced to you. "
        : `${count} people asked to be introduced to you. `, link);
    }
    line.hidden = count === 0;
    document.dispatchEvent(new CustomEvent("resonance:news-changed"));
  }
}

function requestRow(row, kind) {
  const line = el("div", {className: "collab-request"});
  line.dataset.introId = row.intro_id;
  line.dataset.state = row.state;
  const who = el("div", {className: "collab-request__who"});
  // counterpart_display and message are untrusted UGC -> textContent only.
  who.append(
    el("strong", {textContent: row.counterpart_display}),
    el("span", {className: "collab-muted", textContent: kind === "incoming"
      ? "asked to be introduced to you" : "you asked for an introduction"}),
    el("span", {className: "collab-request__when", textContent: relativeTime(row.updated_at || row.created_at)}),
  );
  const badge = el("span", {className: "collab-state", textContent: row.state});
  badge.dataset.state = row.state;
  line.append(who, badge);
  if (row.message) {
    line.append(kind === "incoming"
      ? theirWords(row.message, row.counterpart_display)
      : el("p", {className: "collab-request__message collab-muted", textContent: `You wrote: ${row.message}`}));
  }
  const actions = el("div", {className: "collab-request__actions"});
  if (kind === "incoming" && row.state === "requested") {
    actions.append(actionButton("Accept", () => respond(row.intro_id, true), "primary"));
    actions.append(actionButton("Decline", () => respond(row.intro_id, false)));
  }
  if (kind === "outgoing" && row.state === "requested") {
    actions.append(actionButton("Cancel the request", () => cancel(row.intro_id), "quiet"));
  }
  if (row.state === "accepted") {
    actions.append(actionButton("Open conversation", () => openChannel(row), "primary"));
  }
  if (actions.childElementCount) line.append(actions);
  return line;
}

async function refreshRequests() {
  const host = byId("collab-requests");
  let data;
  try {
    data = await apiFetch("GET", "/api/product/intro/list");
  } catch (error) {
    showError(error.message);
    return;
  }
  state.requests = {incoming: data.incoming || [], outgoing: data.outgoing || []};
  // A request or an answer from someone else changes the state a card shows
  // for that person. Re-read the discovery (a rate-limited action) only when
  // the set of intros actually changed, never on every poll.
  const signature = [...state.requests.incoming, ...state.requests.outgoing]
    .map((row) => `${row.intro_id}:${row.state}`).sort().join(",");
  const changed = state.requestSignature !== undefined && signature !== state.requestSignature;
  state.requestSignature = signature;
  if (changed) refreshInitiate().then(attachMatchCardButtons);
  const incoming = state.requests.incoming;
  const outgoing = state.requests.outgoing;
  const waiting = incoming.filter((row) => row.state === "requested");
  setBadge(waiting.length);

  // The section is part of the loop, so it is on the page whenever the
  // person has shared something or has ever been asked; it is not shown to a
  // visitor who cannot have either.
  const section = byId("conversations");
  const hasAny = incoming.length + outgoing.length > 0;
  if (section) section.hidden = !(hasAny || state.querySession);
  if (!host) return;

  host.replaceChildren(el("h3", {textContent: "Introductions"}));
  const open = [
    ...waiting.map((row) => ["incoming", row]),
    ...outgoing.filter((row) => row.state === "requested").map((row) => ["outgoing", row]),
  ];
  const connected = [
    ...incoming.filter((row) => row.state === "accepted").map((row) => ["incoming", row]),
    ...outgoing.filter((row) => row.state === "accepted").map((row) => ["outgoing", row]),
  ];
  const closed = [
    ...incoming.filter((row) => ["declined", "cancelled"].includes(row.state)).map((row) => ["incoming", row]),
    ...outgoing.filter((row) => ["declined", "cancelled"].includes(row.state)).map((row) => ["outgoing", row]),
  ];
  if (!hasAny) {
    host.append(el("p", {className: "collab-empty", textContent:
      "Nobody has asked yet, and you have not asked anyone. When you do — or someone asks you — it appears here, and nothing opens until both of you agree."}));
  }
  if (waiting.length) {
    host.append(el("h4", {textContent: `Waiting for your answer · ${waiting.length}`}));
    for (const [kind, row] of open.filter(([k]) => k === "incoming")) host.append(requestRow(row, kind));
  }
  const sent = open.filter(([k]) => k === "outgoing");
  if (sent.length) {
    host.append(el("h4", {textContent: `Waiting for their answer · ${sent.length}`}));
    for (const [kind, row] of sent) host.append(requestRow(row, kind));
  }
  if (connected.length) {
    host.append(el("h4", {textContent: `Connected · ${connected.length}`}));
    for (const [kind, row] of connected) host.append(requestRow(row, kind));
  }
  if (closed.length) {
    const details = el("details", {className: "collab-closed"});
    details.append(el("summary", {textContent: `Closed · ${closed.length}`}));
    for (const [kind, row] of closed) details.append(requestRow(row, kind));
    host.append(details);
  }
  // Step 5 without a click: when exactly one conversation is open and none
  // is on screen, show it.
  if (!state.openChannelId && connected.length === 1 && connected[0][1].channel_id) {
    await openChannel(connected[0][1]);
  } else if (!state.openChannelId) {
    renderNoChannel(connected.length);
  }
}

async function requestIntro(fromSessionId, targetSessionId, message) {
  await apiFetch("POST", "/api/product/intro/request", {
    from_session_id: fromSessionId, target_session_id: targetSessionId,
    message, request_id: requestId("req"), confirmed: true,
  });
  await refreshRequests();
}

async function respond(introId, accept) {
  await apiFetch("POST", "/api/product/intro/respond", {
    intro_id: introId, accept, request_id: requestId("resp"), confirmed: true,
  });
  await refreshRequests();
}

async function cancel(introId) {
  await apiFetch("POST", "/api/product/intro/cancel", {
    intro_id: introId, request_id: requestId("cxl"), confirmed: true,
  });
  await refreshRequests();
}

// ---- channel ------------------------------------------------------------

function renderNoChannel(connectedCount) {
  const host = byId("collab-channel");
  if (!host) return;
  host.replaceChildren(
    el("h3", {textContent: "Conversation"}),
    el("p", {className: "collab-empty", textContent: connectedCount > 0
      ? "Open one of the connected introductions to read its conversation."
      : "A conversation opens here once someone accepts — or once you accept someone. Only what is typed here is passed on."}),
  );
}

async function openChannel(introRow) {
  const host = byId("collab-channel");
  if (!host) return;
  // An accepted intro DTO already carries its channel id (no re-accept).
  const channelId = introRow.channel_id;
  if (!channelId) { showError("channel unavailable"); return; }
  state.openChannelId = channelId;
  state.openCounterpart = introRow.counterpart_display || "";
  host.dataset.channelId = channelId;
  const head = el("div", {className: "collab-channel-head"});
  head.append(
    el("h3", {textContent: `Conversation with ${introRow.counterpart_display}`}),
    el("span", {className: "collab-muted", textContent: "Relay only · no contact details are exchanged"}),
  );
  host.replaceChildren(head);
  const thread = el("div", {id: "collab-thread", className: "collab-thread", role: "log"});
  thread.setAttribute("aria-live", "polite");
  const input = el("input", {id: "collab-message-input", type: "text",
    className: "collab-input", maxLength: 2000,
    placeholder: "Write a message"});
  input.setAttribute("aria-label", `Message to ${introRow.counterpart_display}`);
  const sendButton = actionButton("Send", async () => {
    if (!input.value.trim()) return;
    await apiFetch("POST", "/api/product/channel/send", {
      channel_id: channelId, body: input.value.trim(),
      request_id: requestId("msg"), confirmed: true,
    });
    input.value = "";
    await renderThread(channelId, thread);
  }, "primary");
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); sendButton.click(); }
  });
  host.append(thread, el("div", {className: "collab-compose"}, [input, sendButton]));
  await renderThread(channelId, thread);
  byId("conversations")?.removeAttribute("hidden");
}

async function renderThread(channelId, thread) {
  const data = await apiFetch(
    "GET", `/api/product/channel/messages?channel_id=${encodeURIComponent(channelId)}`);
  const stickToEnd = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 40;
  thread.replaceChildren();
  for (const message of data.messages) {
    const mine = message.author === "me";
    // message.body is untrusted UGC -> textContent, never innerHTML.
    const bubble = el("div", {className: mine ? "collab-message is-mine" : "collab-message is-theirs"});
    const meta = el("div", {className: "collab-message__meta"});
    meta.append(el("strong", {textContent: mine ? "You" : message.author_display}),
                el("span", {textContent: relativeTime(message.created_at)}));
    bubble.append(meta, el("p", {textContent: message.body}));
    thread.append(bubble);
  }
  if (stickToEnd) thread.scrollTop = thread.scrollHeight;
}

async function refreshOpenChannel() {
  const thread = byId("collab-thread");
  const channelId = state.openChannelId;
  if (!channelId || !thread) return;
  try { await renderThread(channelId, thread); } catch (error) { showError(error.message); }
}

// ---- match-card enhancement -------------------------------------------

function attachMatchCardButtons() {
  // Progressive enhancement: the "ask for an introduction" action on every
  // card, from the intro state the last authorized read returned. The card
  // exposes its session id; the query session is the person's own
  // discoverable thought.
  for (const card of document.querySelectorAll(".match-card[data-session-id]")) {
    let host = card.querySelector(".match-card__actions");
    if (!host) {
      host = el("div", {className: "match-card__actions"});
      card.append(host);
    }
    if (host.querySelector(".intro-composer")) continue;   // never wipe what someone is typing
    actionsFor(card.dataset.sessionId, host, {
      who: card.dataset.person || "",
      demoPersona: card.dataset.demoPersona === "true",
    });
  }
  // The roster lists people without a card. Cards can render after the
  // roster did (the page's own discovery is a separate read), so anyone who
  // now has a card leaves the roster.
  const onPage = new Set([...document.querySelectorAll(".match-card[data-session-id]")]
    .map((card) => card.dataset.sessionId));
  const roster = byId("collab-initiate");
  if (roster) {
    for (const row of roster.querySelectorAll(".collab-initiate-row")) {
      if (onPage.has(row.dataset.sessionId)) row.remove();
    }
    if (!roster.querySelector(".collab-initiate-row")) roster.replaceChildren();
  }
}

// ---- refresh orchestration ----------------------------------------------

async function refreshAll() {
  let owned = null;
  try { owned = await ownedSessions(); } catch (error) { showError(error.message); }
  await Promise.all([refreshShare(), refreshInitiate(owned), refreshRequests(), refreshOpenChannel()]);
  attachMatchCardButtons();
}

function scheduleRefresh() {
  // Coalesce bursts of writes (e.g. prepare → share from an agent) into one read.
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => { refreshAll(); }, 150);
}

function init() {
  if (!byId("collab-requests") && !byId("share-control")) return;   // not this page
  renderConnect();
  refreshAll();
  // Any successful write through session.mjs (WebMCP tools, workspace tools,
  // this page) re-reads the authorized record so nothing here goes stale.
  document.addEventListener("resonance:write", (event) => {
    // The news band recording that its cards were seen is bookkeeping, not a
    // change in anything this module shows; a re-read here would cost a
    // rate-limited discovery for nothing.
    if (event.detail?.path === "/api/product/resonances/seen") return;
    scheduleRefresh();
  });
  // Older callers asked for the drawer to open; the section is the page now.
  document.addEventListener("resonance:collab-open", () => {
    byId("conversations")?.scrollIntoView({block: "start"});
  });
  // Signed out where a sign-in exists: there is no account to read for, so
  // there is nothing to compose into. The gate is the page.
  document.addEventListener("resonance:sign-in-required", () => {
    byId("share-composer")?.replaceChildren();
    byId("share-state")?.replaceChildren();
  });
  // Requests and messages from other people arrive without a local write:
  // poll slowly while the tab is visible.
  clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (document.visibilityState === "visible") { refreshRequests(); refreshOpenChannel(); }
  }, 20000);
  // Re-attach when the match list re-renders.
  const observer = new MutationObserver(() => attachMatchCardButtons());
  const list = byId("match-list");
  if (list) observer.observe(list, {childList: true});
}

// Without a document (the test suite runs the words above under node)
// there is nothing to render into, and nothing here should run.
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}

export {
  init, refreshAll, refreshRequests, requestIntro, respond, cancel, openChannel,
  introComposer, introStateFor, actionsFor, relativeTime,
};
