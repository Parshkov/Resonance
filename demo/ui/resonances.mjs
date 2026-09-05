/**
 * The half of the product that waits, on the page.
 *
 * A shared thought keeps looking after the first search returns nothing.
 * What it found while the person was not looking is read from
 * /api/product/resonances and shown at the top of the page, before anything
 * else — because nothing the person could do themselves would have found it.
 *
 * Two kinds of finding, rendered differently on purpose:
 *   reason = "they_arrived"  someone new turned up AFTER you shared. No
 *                            search you could run would have found them,
 *                            because they were not there when you searched.
 *                            This carries the weight.
 *   reason = "you_shared"    a resonance that already existed when you
 *                            shared. Ordinary; listed quietly.
 *
 * An alert is a pointer at two sessions, not a snapshot of a person. What is
 * shown about the other side is only what they consented to display. Marking
 * an alert "seen" happens when it has actually been on screen; dismissing is
 * the person's own act. Asking for an introduction reuses collab_ui.mjs so
 * an alert, a card and a roster row all drive the same authorized path.
 */

import { ensureSession, apiFetch } from "/session.mjs";
import { actionsFor, relativeTime } from "/collab_ui.mjs";

const POLL_MS = 30000;
let pollTimer = null;
let refreshTimer = null;
let seenObserver = null;
const pendingSeen = new Set();
let lastAlerts = [];
const shownAsNew = new Set();      // keys first shown as new during this visit

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of [].concat(children)) {
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function byId(id) { return document.getElementById(id); }

function formatScore(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "—";
}

// The section is shared with collab_ui.mjs, which puts the "people asked to
// be introduced" line in it. It is on the page when either has something.
function syncNewsVisibility() {
  const section = byId("news");
  if (!section) return;
  const arrivals = byId("news-arrivals");
  const existing = byId("news-existing");
  const requests = byId("news-requests");
  const hasAlerts = (arrivals?.childElementCount || 0) + (existing?.childElementCount || 0) > 0;
  const hasRequests = requests && !requests.hidden;
  section.hidden = !(hasAlerts || hasRequests);
  const nav = byId("nav-news");
  if (nav) nav.hidden = section.hidden;
}

function describe(alert) {
  // Only consented display fields are present; say what is there, invent
  // nothing about who they are.
  const topic = alert.display?.topic;
  const domain = alert.display?.domain;
  if (topic && domain) return {title: topic, sub: `in ${domain}`};
  if (topic) return {title: topic, sub: ""};
  if (domain) return {title: `A thought in ${domain}`, sub: ""};
  return {title: "A thought with the same shape as yours", sub: "they chose not to show a topic"};
}

function alertCard(alert, quiet) {
  const later = alert.reason === "they_arrived";
  const fresh = !alert.seen_at || shownAsNew.has(alert.alert_key);
  if (fresh) shownAsNew.add(alert.alert_key);
  const card = el("article", {className: `arrival${later ? " is-later" : ""}${fresh ? " is-new" : ""}${quiet ? " is-quiet" : ""}`});
  card.dataset.alertKey = alert.alert_key;
  card.dataset.sessionId = alert.their_session_id;
  card.dataset.unseen = String(!alert.seen_at);      // what the record says, for the seen write
  card.setAttribute("aria-label", later ? "Someone arrived after you shared" : "A resonance that was already here");

  const kicker = el("p", {className: "arrival-kicker eyebrow"});
  if (fresh) kicker.append(el("span", {className: "arrival-new", textContent: "new"}));
  kicker.append(later ? "Arrived after you shared" : "Already here when you shared");
  const when = relativeTime(alert.detected_at);
  if (when) kicker.append(el("span", {className: "arrival-when", textContent: when}));
  card.append(kicker);

  const {title, sub} = describe(alert);
  const heading = el("h3", {textContent: title});
  card.append(heading);

  const why = el("p", {className: "arrival-why"});
  const structural = alert.scores_at_detection?.structural;
  why.append(later
    ? "Someone new shared a thought whose reasoning has the same shape as yours. "
    : "Their reasoning had the same shape as yours when you shared. ");
  if (sub) why.append(`${sub[0].toUpperCase()}${sub.slice(1)}. `);
  why.append("Structural ", el("code", {textContent: formatScore(structural)}),
    alert.mode ? ` · ${alert.mode}` : "");
  card.append(why);

  const actions = el("div", {className: "arrival-actions"});
  const ask = el("div", {className: "match-card__actions"});
  actionsFor(alert.their_session_id, ask, {
    connectionState: alert.connection_state, fromSessionId: alert.my_session_id,
  });
  actions.append(ask);

  const show = el("button", {type: "button", className: "collab-button collab-button--quiet",
    textContent: "Show on the map"});
  show.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("resonance:focus-session",
      {detail: {sessionId: alert.their_session_id}}));
  });
  actions.append(show);

  const dismiss = el("button", {type: "button", className: "collab-button collab-button--quiet",
    textContent: "Dismiss"});
  dismiss.setAttribute("aria-label", `Dismiss: ${title}`);
  dismiss.addEventListener("click", async () => {
    dismiss.disabled = true;
    try {
      await apiFetch("POST", "/api/product/resonances/dismiss", {alert_key: alert.alert_key});
      card.remove();
      syncNewsVisibility();
      updateSummary(lastAlerts.filter((a) => a.alert_key !== alert.alert_key));
    } catch (error) {
      dismiss.disabled = false;
      byId("collab-error") && (byId("collab-error").textContent = error.message);
    }
  });
  actions.append(dismiss);
  card.append(actions);
  return card;
}

function updateSummary(alerts) {
  lastAlerts = alerts;
  const unseen = alerts.filter((a) => !a.seen_at || shownAsNew.has(a.alert_key)).length;
  const arrived = alerts.filter((a) => a.reason === "they_arrived").length;
  const badge = byId("nav-news-count");
  if (badge) { badge.textContent = String(unseen); badge.hidden = unseen === 0; }
  const summary = byId("news-summary");
  if (summary) {
    const parts = [];
    if (arrived) parts.push(`${arrived} arrived after you shared`);
    if (alerts.length - arrived) parts.push(`${alerts.length - arrived} already here`);
    summary.textContent = parts.join(" · ");
  }
  const heading = byId("news-heading");
  if (heading) {
    heading.textContent = arrived > 0
      ? (arrived === 1 ? "Someone new resonates with your thought" : `${arrived} new people resonate with your thought`)
      : "Your thought kept looking";
  }
}

// "Seen" is recorded when the card has really been on screen, not when the
// page loaded with it somewhere below the fold.
function watchForSeen(cards) {
  if (seenObserver) seenObserver.disconnect();
  const unseenCards = cards.filter((card) => card.dataset.unseen === "true");
  if (!unseenCards.length) return;
  const flush = () => {
    if (!pendingSeen.size) return;
    const keys = [...pendingSeen];
    pendingSeen.clear();
    apiFetch("POST", "/api/product/resonances/seen", {alert_keys: keys}).catch(() => {
      for (const key of keys) pendingSeen.add(key);
    });
  };
  if (!("IntersectionObserver" in window)) {
    for (const card of unseenCards) pendingSeen.add(card.dataset.alertKey);
    setTimeout(flush, 4000);
    return;
  }
  let flushTimer = null;
  seenObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      pendingSeen.add(entry.target.dataset.alertKey);
      seenObserver.unobserve(entry.target);
    }
    clearTimeout(flushTimer);
    flushTimer = setTimeout(flush, 2500);
  }, {threshold: 0.6});
  for (const card of unseenCards) seenObserver.observe(card);
}

// "New" means new since you last looked, and this look is still going on:
// the mark stays until the next visit, whatever the record says meanwhile.
// So a re-render only happens when the set of findings really changed
// (someone arrived, a connection state moved), never because our own
// "seen" write came back.
let lastSignature = null;
function signatureOf(alerts) {
  return alerts.map((a) => `${a.alert_key}:${a.connection_state || ""}`).sort().join("|");
}

function render(payload, force = false) {
  const arrivals = byId("news-arrivals");
  const existing = byId("news-existing");
  if (!arrivals || !existing) return;
  const alerts = Array.isArray(payload?.alerts) ? payload.alerts : [];
  const signature = signatureOf(alerts);
  if (!force && signature === lastSignature) return;
  lastSignature = signature;
  arrivals.replaceChildren();
  existing.replaceChildren();
  const cards = [];
  const later = alerts.filter((a) => a.reason === "they_arrived");
  const already = alerts.filter((a) => a.reason !== "they_arrived");
  for (const alert of later) {
    const card = alertCard(alert, false);
    arrivals.append(card);
    cards.push(card);
  }
  if (already.length) {
    const unseenAlready = already.filter((a) => !a.seen_at);
    const details = el("details", {open: unseenAlready.length > 0});
    details.append(el("summary", {textContent:
      `${already.length} ${already.length === 1 ? "person was" : "people were"} already here when you shared`}));
    for (const alert of already) {
      const card = alertCard(alert, true);
      details.append(card);
      cards.push(card);
    }
    existing.append(details);
  }
  updateSummary(alerts);
  syncNewsVisibility();
  watchForSeen(cards);
}

async function refresh() {
  const section = byId("news");
  if (!section) return;
  try {
    await ensureSession();
  } catch {
    return;                                   // signed out: nothing to read
  }
  let response;
  try {
    response = await fetch("/api/product/resonances?include_seen=1",
      {credentials: "same-origin", cache: "no-store"});
  } catch {
    return;
  }
  if (!response.ok) {
    // 401 before a session exists, or a deployment without the standing
    // search: nothing to show, and nothing to say.
    return;
  }
  const payload = await response.json().catch(() => null);
  if (!payload || payload.available === false) return;
  render(payload);
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refresh, 250);
}

function init() {
  if (!byId("news")) return;
  refresh();
  // A share of your own can create "you_shared" alerts at once; an intro you
  // send changes the connection state on a card.
  document.addEventListener("resonance:write", (event) => {
    if (event.detail?.path === "/api/product/resonances/seen") return;   // our own bookkeeping
    scheduleRefresh();
  });
  document.addEventListener("resonance:news-changed", syncNewsVisibility);
  // Arrivals happen without any local write. Poll while the tab is visible,
  // and once more the moment it becomes visible again.
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

export { init, refresh, render, describe };
