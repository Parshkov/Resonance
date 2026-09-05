/**
 * R13B deep links: open a specific authorized match from the URL fragment.
 *
 * `/#match=<result_id>:<session_id>` resolves through the authorized
 * stored-result path (`/api/product/match`) with the viewer's own cookie
 * session. Fail-closed: foreign, stale, or unauthenticated references render
 * a typed message and never a partial match view. Additive module — served
 * and injected only by the live product server; accepted R9/R10 files are
 * untouched.
 */

const FRAGMENT_RE = /^#match=(result-[0-9a-f]{24}):([A-Za-z0-9._-]+)$/;

function byId(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const node = byId(id);
  if (node) node.textContent = value;
}

function failClosed(message) {
  setText("evidence-kicker", "Deep link");
  setText("evidence-heading", "Link cannot be opened");
  setText("evidence-subtitle", message);
  setText("metric-class", "—");
  setText("metric-structural", "—");
  setText("metric-confidence", "—");
  const list = byId("mapping-list");
  if (list) list.replaceChildren();
}

function renderMatch(payload) {
  const match = payload.match || {};
  const scores = match.scores || {};
  const evidence = match.evidence || {};
  const display = match.display || {};
  setText("evidence-kicker", "Opened from link");
  setText("evidence-heading",
          display.topic || match.person_pseudonym || "resonance match");
  setText("evidence-subtitle",
          `${match.person_pseudonym || "anonymous"} · ` +
          `${evidence.preserved_relation_count ?? 0} preserved relations`);
  setText("metric-class", match.mode_classification || "—");
  setText("metric-structural",
          scores.structural !== undefined ? String(scores.structural) : "—");
  setText("metric-confidence", match.confidence || "—");
  const list = byId("mapping-list");
  if (list) {
    list.replaceChildren();
    for (const pair of evidence.top_correspondences || []) {
      const row = document.createElement("div");
      row.className = "mapping-row";
      const query = document.createElement("div");
      query.className = "mapping-side";
      const queryId = document.createElement("small");
      queryId.textContent = pair.query_node || "";
      const queryLabel = document.createElement("strong");
      queryLabel.textContent = pair.query_label || "";
      query.append(queryId, queryLabel);
      const arrow = document.createElement("div");
      arrow.className = "mapping-arrow";
      arrow.textContent = "↔";
      const candidate = document.createElement("div");
      candidate.className = "mapping-side";
      const candidateId = document.createElement("small");
      candidateId.textContent = pair.candidate_node || "";
      const candidateLabel = document.createElement("strong");
      candidateLabel.textContent = pair.candidate_label || "";
      candidate.append(candidateId, candidateLabel);
      row.append(query, arrow, candidate);
      list.appendChild(row);
    }
  }
  // Progressive enhancement: highlight the card when it is on screen.
  const selector = `.match-card[data-session-id="${CSS.escape(match.session_id || "")}"]`;
  document.querySelector(selector)?.click();
}

async function openFromFragment() {
  const parsed = FRAGMENT_RE.exec(window.location.hash || "");
  if (!parsed) return;
  const [, resultId, sessionId] = parsed;
  let response;
  try {
    response = await fetch(
      `/api/product/match?result_id=${encodeURIComponent(resultId)}` +
      `&session_id=${encodeURIComponent(sessionId)}`,
      {credentials: "same-origin"});
  } catch {
    failClosed("network error while resolving the link");
    return;
  }
  if (response.status === 401) {
    failClosed("sign in first, then reopen this link");
    return;
  }
  if (response.status === 409) {
    failClosed("results changed since this link was made — run discovery again");
    return;
  }
  if (!response.ok) {
    failClosed("this link is not yours, expired, or no longer available");
    return;
  }
  try {
    renderMatch(await response.json());
  } catch {
    failClosed("malformed link response");
  }
}

window.addEventListener("hashchange", openFromFragment);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", openFromFragment);
} else {
  openFromFragment();
}

export { FRAGMENT_RE, openFromFragment };
