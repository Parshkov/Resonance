/**
 * Shared topics, on the page.
 *
 * After an introduction, two people do not trade messages here; each adds
 * what they now understand, as structure plus a short note they approved,
 * and the topic is what those contributions say together: where the accounts
 * agree, and where they contradict each other, which is usually the reason
 * the introduction was worth making. A topic can hold more than two people.
 *
 * Until now this existed only for someone in a chat. This module puts the
 * same thing on the site, over the same service the chat tools use:
 *
 *   /api/product/topics             every topic you are in, and invitations
 *   /api/product/topic              what is new for you, and where it stands
 *   /api/product/topic/preview      your words shown back as structure
 *   /api/product/topic/contribute   the structure and note you approved
 *   /api/product/topic/invite       bring in someone you were introduced to
 *
 * The section is built beside #topics-anchor, as a direct child of the main
 * column so the navigation picks it up, and it is on the page only when there
 * is something in it: a topic, an invitation, or an accepted introduction a
 * topic could be opened on. Like every other section, absent is the honest
 * state when there is nothing.
 *
 * Every read is a delta since this reader's cursor. Showing the new
 * contributions is what moves the cursor, so nothing is marked read by a
 * page load or a poll — only by the person asking to see it. Everything
 * another participant wrote is inserted as text, never markup, and is marked
 * as theirs.
 */

import { apiFetch, getCsrf } from "/session.mjs";
import { relativeTime } from "/collab_ui.mjs";
import { buildNav } from "/shell.mjs";

const POLL_MS = 20000;
const NOTE_MAX = 1000;
const TEXT_MAX = 4000;

const PLACEHOLDER =
  "What do you now understand about this? Say what causes what, what prevents what, " +
  "what requires what — the structure comes from those words, and the words themselves " +
  "are not kept.";

const TRUST =
  "Your words are not kept. Only the structure, and the note you approve, reach the others.";

// The engine's word for how two accounts relate, said to a person. "negative"
// is what it says when it would not have called the two the same thought; the
// agreements and differences below still stand, so it is a reading, not a
// verdict, and it is never painted as a fault.
const CLASSIFICATION = {
  direct: "the same reasoning",
  approximate: "nearly the same reasoning",
  analogical: "the same shape in different words",
  complementary: "shapes that complete each other",
  negative: "not the same thought",
};

const CONFIDENCE = {
  high: " and is sure of it",
  medium: " and is fairly sure of it",
  low: " but is not sure of it",
};

const CONTESTED_KIND = {
  relation_type: "the same link, a different kind",
  assertion: "one account asserts what the other denies",
  polarity: "the two point opposite ways",
};

let requestCounter = 0;
let refreshTimer = null;
let pollTimer = null;
let sharedThought;                 // undefined: not asked yet; null: nothing shared

const state = {
  viewer: "",
  topics: [],
  invitations: [],
  connections: [],                 // accepted introductions, one per person
  panels: new Map(),               // workspace_id -> the parts of its panel
  shown: new Map(),                // workspace_id -> contributions on screen
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

function requestId(prefix) {
  requestCounter += 1;
  return `ui-topic-${prefix}-${Date.now().toString(36)}-${requestCounter}-${getCsrf()?.slice(0, 6) || "anon"}`;
}

function showError(message) {
  if (message && /^Sign in to Resonance/.test(message)) return;
  document.dispatchEvent(new CustomEvent("resonance:notice", {detail: {message: message || ""}}));
}

function toast(message) {
  if (!message) return;
  document.dispatchEvent(new CustomEvent("resonance:toast", {detail: {message}}));
}

// The service states a reason in lower case and without a full stop, as a
// clause an assistant would fold into its own sentence. On a page it stands
// alone, so it is given the shape of one.
function sentence(text) {
  const plain = String(text || "").trim();
  if (!plain) return "";
  const capital = plain.charAt(0).toUpperCase() + plain.slice(1);
  return /[.!?]$/.test(capital) ? capital : `${capital}.`;
}

function humanRelation(type) {
  return String(type || "").replace(/_/g, " ");
}

function button(label, handler, variant = "") {
  const className = variant === "primary" ? "collab-button collab-button--primary"
    : variant === "quiet" ? "collab-button collab-button--quiet" : "collab-button";
  const node = el("button", {type: "button", textContent: label, className});
  node.addEventListener("click", async () => {
    node.disabled = true;
    showError("");
    try { await handler(); } catch (error) { showError(error.message); }
    node.disabled = false;
  });
  return node;
}

// Names, as a person would list them: "Bea", "Bea and Cai", "Bea, Cai and Dov".
function listNames(names) {
  const list = names.filter(Boolean);
  if (list.length <= 1) return list[0] || "";
  return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}

// ---- the section ----------------------------------------------------------

function section() {
  let node = byId("topics");
  if (node) return node;
  const anchor = byId("topics-anchor");
  if (!anchor) return null;
  node = el("section", {className: "topics", id: "topics", hidden: true});
  node.setAttribute("aria-labelledby", "topics-heading");
  node.setAttribute("data-nav-label", "Topics");
  const head = el("div", {className: "section-head"}, [
    el("div", {}, [
      el("h2", {id: "topics-heading", textContent: "Shared topics"}),
      el("p", {className: "section-status", textContent:
        "After an introduction, what builds up between you is not a transcript. Each of you " +
        "adds what you now understand, and the topic says where you agree and where you " +
        "contradict each other."}),
    ]),
  ]);
  node.append(
    head,
    el("div", {className: "topics-invitations", id: "topics-invitations"}),
    el("div", {className: "topics-list", id: "topics-list"}),
    el("div", {className: "topics-open", id: "topics-open"}),
  );
  // Beside the anchor, not inside it: the navigation lists the direct
  // children of the main column, and this is one of them.
  anchor.insertAdjacentElement("afterend", node);
  return node;
}

// ---- structure, shown as the page shows every other thought ------------------

function structure(thought, label) {
  const nodes = Array.isArray(thought?.nodes) ? thought.nodes : [];
  const relations = Array.isArray(thought?.relations) ? thought.relations : [];
  const labelOf = new Map(nodes.map((n) => [n.id, n.label]));
  const box = el("div", {className: "topic-structure"});
  const chain = el("ol", {className: "dna-chain"});
  chain.setAttribute("aria-label", `${label}: nodes`);
  for (const node of nodes) {
    const row = el("li", {className: "dna-node"});
    row.append(el("strong", {textContent: node.label || ""}), el("span", {textContent: node.role || ""}));
    chain.append(row);
  }
  const list = el("ol", {className: "dna-relations"});
  list.setAttribute("aria-label", `${label}: relations`);
  for (const relation of relations) {
    const row = el("li", {className: "dna-relation"});
    row.append(
      el("span", {textContent: labelOf.get(relation.source) || ""}),
      el("span", {className: "relation-type", textContent: humanRelation(relation.type)}),
      el("span", {textContent: labelOf.get(relation.target) || ""}),
    );
    list.append(row);
  }
  box.append(chain, list);
  return box;
}

// ---- where the topic stands --------------------------------------------------

function standingView(standing) {
  const box = el("div", {className: "standing"});
  box.append(el("h4", {className: "eyebrow", textContent: "Where this stands"}));
  if (!standing?.available) {
    box.append(el("p", {className: "standing__empty", textContent:
      sentence(standing?.reason) || "Add your own understanding, and the topic can say where it agrees with theirs."}));
    return box;
  }
  if (!standing.sides?.length) {
    box.append(el("p", {className: "standing__empty", textContent:
      "Only you have added anything so far. When someone else does, this is where the two accounts are compared."}));
    return box;
  }
  for (const side of standing.sides) {
    const card = el("article", {className: "standing__side"});
    const reading = CLASSIFICATION[side.classification] || "";
    const sure = CONFIDENCE[side.confidence] || "";
    card.append(el("h5", {className: "standing__with", textContent: `You and ${side.with_pseudonym || "them"}`}));
    if (reading) {
      card.append(el("p", {className: "standing__reading", textContent:
        `The engine reads these as ${reading}${sure}.`}));
    }

    const contested = Array.isArray(side.contested) ? side.contested : [];
    if (contested.length) {
      const block = el("div", {className: "standing__block standing__block--contested"});
      block.append(el("p", {className: "standing__label", textContent:
        contested.length === 1 ? "Where the two accounts contradict each other"
          : `Where the two accounts contradict each other, ${contested.length} times`}));
      const list = el("ul", {className: "contested"});
      for (const item of contested) {
        const row = el("li", {className: "contested__item"});
        row.append(
          el("span", {className: "contested__side"}, [el("b", {textContent: "You: "}), item.yours || ""]),
          el("span", {className: "contested__side"}, [el("b", {textContent: `${side.with_pseudonym || "Them"}: `}), item.theirs || ""]),
        );
        const kind = CONTESTED_KIND[item.kind] || humanRelation(item.kind);
        if (kind) row.append(el("span", {className: "contested__kind", textContent: kind}));
        list.append(row);
      }
      block.append(list);
      card.append(block);
    }

    const agreed = Array.isArray(side.agreed_nodes) ? side.agreed_nodes : [];
    const block = el("div", {className: "standing__block"});
    const links = Number(side.agreed_relations || 0);
    const summary = agreed.length
      ? `You both carry ${agreed.length === 1 ? "one point" : `${agreed.length} points`}` +
        (links ? ` and ${links === 1 ? "one link" : `${links} links`} between them` : "")
      : "Nothing yet that both accounts carry";
    block.append(el("p", {className: "standing__label", textContent: summary}));
    if (agreed.length) {
      const list = el("ul", {className: "agreed"});
      for (const pair of agreed) {
        const row = el("li", {className: "agreed__pair"});
        if (pair.yours === pair.theirs) {
          row.append(el("span", {textContent: pair.yours || ""}));
        } else {
          row.append(
            el("span", {textContent: pair.yours || ""}),
            el("span", {className: "agreed__arrow", textContent: "↔"}),
            el("span", {textContent: pair.theirs || ""}),
          );
        }
        list.append(row);
      }
      block.append(list);
    }
    card.append(block);

    const yoursOnly = Array.isArray(side.yours_unanswered) ? side.yours_unanswered : [];
    const theirsOnly = Array.isArray(side.theirs_unanswered) ? side.theirs_unanswered : [];
    if (yoursOnly.length || theirsOnly.length) {
      const open = el("div", {className: "standing__block standing__block--open"});
      if (yoursOnly.length) {
        open.append(el("p", {className: "standing__only"}, [
          el("b", {textContent: "Only in yours: "}), yoursOnly.join(", ")]));
      }
      if (theirsOnly.length) {
        open.append(el("p", {className: "standing__only"}, [
          el("b", {textContent: `Only in ${side.with_pseudonym || "theirs"}'s: `}), theirsOnly.join(", ")]));
      }
      card.append(open);
    }
    box.append(card);
  }
  return box;
}

// ---- what is new -----------------------------------------------------------------

function contributionView(item) {
  const card = el("article", {className: "contribution"});
  const who = item.author_pseudonym || "someone";
  const head = el("div", {className: "contribution__head"});
  head.append(el("strong", {className: "contribution__who", textContent: who}));
  const when = relativeTime(item.created_at);
  if (when) head.append(el("span", {className: "contribution__when", textContent: when}));
  card.append(head);
  if (item.note) {
    const note = el("p", {className: "their-words", textContent: item.note});
    note.dataset.from = who;
    card.append(note);
  }
  card.append(structure(item.thought, `What ${who} added`));
  return card;
}

function newsView(topic, parts) {
  const box = parts.news;
  box.replaceChildren();
  const shown = state.shown.get(topic.workspace_id) || [];
  const waiting = Number(topic.new_for_you || 0);
  box.append(el("h4", {className: "eyebrow", textContent: "New since you last looked"}));
  if (waiting > 0) {
    const label = shown.length
      ? (waiting === 1 ? "Show one more" : `Show ${waiting} more`)
      : (waiting === 1 ? "Show the new contribution" : `Show the ${waiting} new contributions`);
    box.append(button(label, async () => {
      // Showing is what moves the cursor: read with advance, keep on screen.
      const read = await apiFetch("GET",
        `/api/product/topic?workspace_id=${encodeURIComponent(topic.workspace_id)}&advance=1`);
      const seen = state.shown.get(topic.workspace_id) || [];
      state.shown.set(topic.workspace_id, seen.concat(read.delta || []));
      if (read.truncated) toast("Only the most recent ones are shown; look again for the rest.");
      topic.new_for_you = 0;
      parts.standing.replaceWith(standingView(read.standing));
      parts.standing = parts.panel.querySelector(".standing");
      newsView(topic, parts);
      syncNav();
    }, "primary"));
  } else if (!shown.length) {
    box.append(el("p", {className: "topic-quiet", textContent:
      Number(topic.contributions_total || 0) > 0
        ? "Nothing new since you last looked."
        : "Nothing has been added yet. What you add first is what the others will read."}));
  }
  if (shown.length) {
    const list = el("div", {className: "contributions"});
    for (const item of shown) list.append(contributionView(item));
    box.append(list);
  }
}

// ---- adding what you now understand ------------------------------------------------

async function thoughtYouShared() {
  if (sharedThought !== undefined) return sharedThought;
  try {
    const response = await fetch("/api/context", {credentials: "same-origin"});
    if (!response.ok) { sharedThought = null; return null; }
    const context = await response.json();
    const thought = context?.active_thought;
    const nodes = Array.isArray(thought?.nodes) ? thought.nodes : [];
    const relations = Array.isArray(thought?.relations) ? thought.relations : [];
    sharedThought = nodes.length >= 2 && relations.length ? {
      nodes: nodes.map((n) => ({id: n.id, label: n.label, role: n.role})),
      relations: relations.map((r) => ({source: r.source, target: r.target, type: r.type})),
    } : null;
  } catch {
    sharedThought = null;
  }
  return sharedThought;
}

function composer(topic) {
  const form = el("form", {className: "topic-form"});
  const id = `topic-text-${topic.workspace_id.replace(/[^A-Za-z0-9_-]/g, "")}`;
  form.append(el("h4", {className: "eyebrow", textContent: "Add what you now understand"}));
  form.append(el("label", {htmlFor: id, className: "visually-hidden", textContent: "What you now understand, in your own words"}));
  const textarea = el("textarea", {id, name: "context", required: true, maxLength: TEXT_MAX,
    placeholder: PLACEHOLDER, rows: 5});
  const status = el("p", {className: "topic-form__status", role: "status"});
  const row = el("div", {className: "topic-form__row"});
  const extract = el("button", {type: "submit", className: "collab-button collab-button--primary",
    textContent: "Show me the structure"});
  const reuse = el("button", {type: "button", className: "collab-button collab-button--quiet",
    textContent: "Use the thought you shared", hidden: true});
  row.append(extract, reuse, el("p", {className: "topic-form__trust", textContent: TRUST}));
  form.append(textarea, row, status);

  thoughtYouShared().then((thought) => { reuse.hidden = !thought; });

  const fail = (error) => {
    status.classList.add("is-error");
    status.textContent = error.message;
  };

  // Step two: the structure shown back, a note, and the explicit add.
  const review = (thought) => {
    const box = el("section", {className: "topic-preview"});
    box.setAttribute("aria-label", "What the others would read");
    box.append(el("h5", {className: "topic-preview__title", textContent: "This is what the others would read"}));
    box.append(structure(thought, "Your contribution"));
    const noteId = `${id}-note`;
    box.append(el("label", {htmlFor: noteId, className: "topic-preview__label", textContent:
      "A short note to go with it, in your own words (optional)"}));
    const note = el("textarea", {id: noteId, name: "note", maxLength: NOTE_MAX, rows: 2,
      placeholder: "For example: slack time is what actually prevents the rework."});
    box.append(note);
    const confirmRow = el("div", {className: "topic-form__row"});
    const add = el("button", {type: "button", className: "collab-button collab-button--primary",
      textContent: "Add this to the topic"});
    const back = el("button", {type: "button", className: "collab-button collab-button--quiet",
      textContent: "Change the text"});
    confirmRow.append(add, back, el("p", {className: "topic-form__trust", textContent:
      "Nothing reaches the others until you add it."}));
    box.append(confirmRow);
    add.addEventListener("click", async () => {
      add.disabled = true;
      status.classList.remove("is-error");
      try {
        const result = await apiFetch("POST", "/api/product/topic/contribute", {
          workspace_id: topic.workspace_id, thought, note: note.value.trim(),
          confirmed: true, request_id: requestId("add"),
        });
        toast(result.say || "Added to the shared topic.");
        box.remove();
        textarea.value = "";
        textarea.hidden = false; row.hidden = false; extract.disabled = false;
        status.textContent = "";
      } catch (error) {
        fail(error);
        add.disabled = false;
      }
    });
    back.addEventListener("click", () => {
      box.remove();
      textarea.hidden = false; row.hidden = false; extract.disabled = false;
      textarea.focus();
    });
    textarea.hidden = true; row.hidden = true;
    form.insertBefore(box, status);
    box.setAttribute("tabindex", "-1");
    box.focus({preventScroll: false});
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const context = textarea.value.trim();
    if (!context) { textarea.focus(); return; }
    extract.disabled = true;
    status.classList.remove("is-error");
    status.textContent = "Reading the structure…";
    try {
      const preview = await apiFetch("POST", "/api/product/topic/preview", {context});
      status.textContent = "";
      review(preview.thought);
    } catch (error) {
      fail(error);
      extract.disabled = false;
    }
  });
  reuse.addEventListener("click", async () => {
    const thought = await thoughtYouShared();
    if (thought) review(thought);
  });
  return form;
}

// ---- bringing someone in -------------------------------------------------------------

function inviteView(topic) {
  const box = el("div", {className: "topic-invite"});
  if (!["owner", "member"].includes(topic.role)) return box;
  const present = new Set((topic.members || []).map((m) => m.pseudonym));
  const candidates = state.connections.filter((c) => !present.has(c.counterpart_display));
  if (!candidates.length) return box;
  box.append(el("h4", {className: "eyebrow", textContent: "Bring someone in"}));
  box.append(el("p", {className: "topic-quiet", textContent:
    "Only someone you have been introduced to. They decide whether to join, and nothing here reaches them until they do."}));
  const row = el("div", {className: "topic-invite__row"});
  for (const person of candidates) {
    row.append(button(`Invite ${person.counterpart_display}`, async () => {
      const result = await apiFetch("POST", "/api/product/topic/invite", {
        workspace_id: topic.workspace_id, intro_id: person.intro_id});
      toast(result.say || "Invited.");
    }));
  }
  box.append(row);
  return box;
}

// ---- one topic ------------------------------------------------------------------------

function membersLine(topic) {
  const others = (topic.members || []).filter((m) => !m.you);
  const active = others.filter((m) => m.state === "active").map((m) => m.pseudonym);
  const invited = others.filter((m) => m.state === "invited").map((m) => m.pseudonym);
  const parts = [];
  if (active.length) parts.push(`With ${listNames(active)}`);
  else parts.push("Nobody else has joined yet");
  if (invited.length) parts.push(`${listNames(invited)} invited, not yet joined`);
  return parts.join(" · ");
}

function topicPanel(topic) {
  let parts = state.panels.get(topic.workspace_id);
  if (!parts) {
    const panel = el("article", {className: "panel topic"});
    panel.setAttribute("aria-label", topic.title || "Shared topic");
    const head = el("div", {className: "topic__head"});
    const standing = el("div", {className: "standing"});
    const news = el("div", {className: "topic-news"});
    const invite = el("div", {className: "topic-invite"});
    panel.append(head, standing, news, composer(topic), invite);
    parts = {panel, head, standing, news, invite};
    state.panels.set(topic.workspace_id, parts);
  }
  parts.head.replaceChildren(
    el("div", {className: "topic__titles"}, [
      el("h3", {className: "topic__title", textContent: topic.title || "Shared topic"}),
      el("p", {className: "topic__members", textContent: membersLine(topic)}),
      topic.brief ? el("p", {className: "topic__brief", textContent: topic.brief}) : "",
    ]),
  );
  if (Number(topic.new_for_you || 0) > 0) {
    parts.head.append(el("span", {className: "topic__badge", textContent:
      topic.new_for_you === 1 ? "1 new" : `${topic.new_for_you} new`}));
  }
  newsView(topic, parts);
  const invite = inviteView(topic);
  parts.invite.replaceWith(invite);
  parts.invite = invite;
  return parts;
}

// The standing is only in a full read; the listing is a glance. Fetched
// without advancing, so painting it marks nothing read.
async function fillStanding(topic, parts) {
  try {
    const read = await apiFetch("GET",
      `/api/product/topic?workspace_id=${encodeURIComponent(topic.workspace_id)}&advance=0`);
    const fresh = standingView(read.standing);
    parts.standing.replaceWith(fresh);
    parts.standing = fresh;
  } catch (error) {
    showError(error.message);
  }
}

// ---- invitations and opening ------------------------------------------------------------

function invitationView(invitation) {
  const card = el("article", {className: "invitation"});
  const who = invitation.invited_by_pseudonym || "Someone";
  card.append(el("p", {className: "invitation__text"}, [
    el("strong", {textContent: who}), " invited you to ",
    el("q", {textContent: invitation.title || "a shared topic"}), ".",
  ]));
  card.append(el("p", {className: "topic-quiet", textContent:
    "Nothing of yours is shared with it until you join, and joining shares only what you choose to add."}));
  const row = el("div", {className: "invitation__row"});
  row.append(
    button("Join", async () => {
      await apiFetch("POST", "/api/product/workspace/respond", {
        workspace_id: invitation.workspace_id, accept: true});
      toast("Joined. You can now read what the others have added, and add your own.");
    }, "primary"),
    button("Not now", async () => {
      await apiFetch("POST", "/api/product/workspace/respond", {
        workspace_id: invitation.workspace_id, accept: false});
      toast("Declined. Nothing of yours was shared with that topic.");
    }, "quiet"),
  );
  card.append(row);
  return card;
}

function openView() {
  const host = byId("topics-open");
  if (!host) return;
  // A poll must not take a half-typed title away from someone.
  if (host.querySelector(".open-topic__form")) return;
  host.replaceChildren();
  if (!state.connections.length) return;
  const body = el("div", {className: "open-topic"});
  body.append(el("p", {className: "topic-quiet", textContent:
    "A topic starts from an introduction that both of you accepted. Give it a title in your own words; " +
    "the other person is invited and decides whether to join."}));
  const row = el("div", {className: "open-topic__row"});
  for (const person of state.connections) {
    const trigger = button(`Open a topic with ${person.counterpart_display}`, async () => {
      if (row.querySelector(".open-topic__form")) return;
      const form = el("form", {className: "open-topic__form"});
      const id = `open-topic-${person.intro_id.replace(/[^A-Za-z0-9_-]/g, "")}`;
      form.append(el("label", {htmlFor: id, textContent: `A title for the topic with ${person.counterpart_display}`}));
      const title = el("input", {id, name: "title", type: "text", required: true, maxLength: 200,
        placeholder: "For example: pressure that backfires"});
      const controls = el("div", {className: "topic-form__row"});
      const open = el("button", {type: "submit", className: "collab-button collab-button--primary", textContent: "Open the topic"});
      const cancel = el("button", {type: "button", className: "collab-button collab-button--quiet", textContent: "Cancel"});
      controls.append(open, cancel);
      form.append(title, controls);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = title.value.trim();
        if (!text) { title.focus(); return; }
        open.disabled = true;
        try {
          await apiFetch("POST", "/api/product/workspace/create", {
            intro_id: person.intro_id, title: text, brief: ""});
          toast(`Opened. ${person.counterpart_display} is invited and decides whether to join.`);
          form.remove();
        } catch (error) {
          showError(error.message);
          open.disabled = false;
        }
      });
      cancel.addEventListener("click", () => form.remove());
      row.append(form);
      queueMicrotask(() => title.focus());
    });
    row.append(trigger);
  }
  body.append(row);
  if (state.topics.length || state.invitations.length) {
    const more = el("details", {className: "open-topic__more"});
    more.append(el("summary", {textContent: "Open another topic"}), body);
    host.append(more);
  } else {
    host.append(el("div", {className: "panel"}, [
      el("h3", {className: "open-topic__title", textContent: "Open a shared topic"}), body]));
  }
}

// ---- refresh --------------------------------------------------------------------------------

// The navigation is built from the sections on the page. The shell watches
// the main column's children, which catches this section arriving; a later
// change of its count or its visibility is announced here.
function syncNav() {
  const node = byId("topics");
  if (!node) return;
  const count = state.topics.reduce((sum, t) => sum + Number(t.new_for_you || 0), 0)
    + state.invitations.length;
  if (count > 0) node.dataset.navCount = String(count);
  else delete node.dataset.navCount;
  buildNav();
}

function render() {
  const node = section();
  if (!node) return;
  const present = state.topics.length || state.invitations.length || state.connections.length;
  if (!present) {
    hide();
    return;
  }
  const invitations = byId("topics-invitations");
  invitations.replaceChildren(...state.invitations.map(invitationView));
  const list = byId("topics-list");
  const keep = new Set(state.topics.map((t) => t.workspace_id));
  for (const [id, parts] of state.panels) {
    if (!keep.has(id)) { parts.panel.remove(); state.panels.delete(id); state.shown.delete(id); }
  }
  for (const topic of state.topics) {
    const parts = topicPanel(topic);
    if (parts.panel.parentNode !== list) list.append(parts.panel);
    fillStanding(topic, parts);
  }
  openView();
  node.hidden = false;
  syncNav();
}

function hide() {
  const node = byId("topics");
  if (!node || node.hidden) return;
  node.hidden = true;
  delete node.dataset.navCount;
  buildNav();
}

async function refresh() {
  let listing, intros;
  try {
    [listing, intros] = await Promise.all([
      apiFetch("GET", "/api/product/topics"),
      apiFetch("GET", "/api/product/intro/list"),
    ]);
  } catch (error) {
    // A request that never reached the server -- the page was navigating,
    // the connection dropped for a moment -- says nothing about this
    // person's topics, so what is on the page stays, and nothing is announced.
    if (error?.name === "TypeError") return;
    // No account here yet: not a fault, an absence. The section leaves; the
    // account module already shows the way in.
    if (/^(Sign in|authentication_failed|401)/.test(error.message || "")) { hide(); return; }
    showError(error.message);
    return;
  }
  state.viewer = listing.viewer_pseudonym || "";
  state.topics = Array.isArray(listing.topics) ? listing.topics : [];
  state.invitations = Array.isArray(listing.invitations) ? listing.invitations : [];
  const accepted = new Map();
  for (const intro of [].concat(intros.incoming || [], intros.outgoing || [])) {
    if (intro.state === "accepted" && intro.counterpart_display && !accepted.has(intro.counterpart_display)) {
      accepted.set(intro.counterpart_display, intro);
    }
  }
  state.connections = [...accepted.values()];
  render();
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refresh, 200);
}

function init() {
  if (!byId("topics-anchor")) return;          // not this page
  refresh();
  document.addEventListener("resonance:write", (event) => {
    if (event.detail?.path === "/api/product/resonances/seen") return;
    scheduleRefresh();
  });
  document.addEventListener("resonance:sign-in-required", hide);
  // Contributions and invitations from other people arrive without any
  // local write: poll slowly while the tab is visible, and once more when it
  // becomes visible again.
  clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (document.visibilityState === "visible") refresh();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") scheduleRefresh();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

export { init, refresh, render };
