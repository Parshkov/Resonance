/**
 * One state for the whole page.
 *
 * Every screen reads from here and nothing else talks to the API directly.
 * The page used to have a dozen modules each fetching on its own and telling
 * the others through DOM events; sections appeared one by one as each fetch
 * landed, and the same record was read two or three times per load. Now there
 * is one read (`/api/product/overview`), one refresh after any write, and one
 * slow poll while the tab is visible.
 *
 * Discovery results and group details are read on demand and cached by id;
 * discovery is rate-limited on the server, so it is never polled.
 */

import { apiFetch, ensureSession } from "/session.mjs";

const POLL_MS = 20000;

const state = {
  phase: "loading",          // loading | ready | signed-out | error
  error: "",
  overview: null,            // /api/product/overview
  discovery: new Map(),      // session_id -> {loading, error, payload}
  geo: new Map(),            // session_id -> {loading, error, payload}
  groups: new Map(),         // workspace_id -> {loading, error, detail, topic}
  stamped: null,             // the account the server wrote into the HTML
};

const listeners = new Set();
let refreshTimer = null;
let pollTimer = null;
let loading = null;
let lastSignature = null;

function emit() {
  for (const fn of listeners) {
    try { fn(state); } catch (error) { console.error(error); }
  }
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getState() { return state; }

// ---- reads -----------------------------------------------------------------

async function readJson(path) {
  const response = await fetch(path, {credentials: "same-origin", cache: "no-store"});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.code = payload.error;
    throw error;
  }
  return payload;
}

export async function load() {
  if (loading) return loading;
  loading = (async () => {
    try {
      await ensureSession();
    } catch (error) {
      if (/^Sign in/.test(error?.message || "")) {
        state.phase = "signed-out";
        state.overview = await readJson("/api/product/overview").catch(() => null);
        emit();
        return;
      }
      state.phase = "error"; state.error = error.message; emit();
      return;
    }
    try {
      let overview = await readJson("/api/product/overview");
      // A CSRF token kept from an earlier visit names a session this server
      // no longer knows (it restarted, or the session was revoked). Where a
      // pseudonymous start is allowed, start again once rather than showing
      // a sign-in that does not exist.
      if (!overview.authenticated && !overview.sign_in_required) {
        await ensureSession({force: true}).catch(() => {});
        overview = await readJson("/api/product/overview");
      }
      // Nothing changed: say nothing. A poll that re-renders an identical
      // screen every twenty seconds is what made elements flicker.
      const signature = JSON.stringify(overview);
      const same = state.phase === "ready" && signature === lastSignature;
      lastSignature = signature;
      state.overview = overview;
      state.phase = overview.authenticated ? "ready" : "signed-out";
      state.error = "";
      if (same) return;
    } catch (error) {
      state.phase = "error"; state.error = error.message;
    }
    emit();
  })().finally(() => { loading = null; });
  return loading;
}

export function refresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => { load(); }, 150);
}

// A group is other people's work too: posts, parts and contributions arrive
// without any write of ours, so a group on screen is re-read on the slow poll.
export const GROUP_STALE_MS = 15000;

export function groupIsStale(workspaceId) {
  const entry = state.groups.get(workspaceId);
  return !!entry && !entry.loading && Date.now() - (entry.fetched_at || 0) > GROUP_STALE_MS;
}

export async function discover(sessionId, {force = false} = {}) {
  if (!sessionId) return null;
  const cached = state.discovery.get(sessionId);
  if (cached && !force && (cached.payload || cached.loading)) return cached.payload;
  state.discovery.set(sessionId, {loading: true, error: "", payload: cached?.payload || null});
  emit();
  try {
    const payload = await readJson(`/api/discover?session_id=${encodeURIComponent(sessionId)}`);
    state.discovery.set(sessionId, {loading: false, error: "", payload});
  } catch (error) {
    state.discovery.set(sessionId, {loading: false, error: error.message, payload: null});
  }
  emit();
  return state.discovery.get(sessionId).payload;
}

export async function geo(sessionId, {force = false} = {}) {
  if (!sessionId) return null;
  const cached = state.geo.get(sessionId);
  if (cached && !force && (cached.payload || cached.loading)) return cached.payload;
  state.geo.set(sessionId, {loading: true, error: "", payload: cached?.payload || null});
  try {
    const payload = await readJson(`/api/geo?session_id=${encodeURIComponent(sessionId)}`);
    state.geo.set(sessionId, {loading: false, error: "", payload});
  } catch (error) {
    state.geo.set(sessionId, {loading: false, error: error.message, payload: null});
  }
  emit();
  return state.geo.get(sessionId).payload;
}

export async function group(workspaceId, {force = false} = {}) {
  if (!workspaceId) return null;
  const cached = state.groups.get(workspaceId);
  if (cached && !force && (cached.detail || cached.loading)) return cached;
  state.groups.set(workspaceId, {loading: true, error: "", detail: cached?.detail || null, topic: cached?.topic || null});
  emit();
  try {
    const [detail, topic] = await Promise.all([
      readJson(`/api/product/workspace?workspace_id=${encodeURIComponent(workspaceId)}`),
      readJson(`/api/product/topic?workspace_id=${encodeURIComponent(workspaceId)}&advance=0&full=1`),
    ]);
    state.groups.set(workspaceId, {loading: false, error: "", detail, topic, fetched_at: Date.now()});
  } catch (error) {
    state.groups.set(workspaceId, {loading: false, error: error.message, detail: null, topic: null, fetched_at: Date.now()});
  }
  emit();
  return state.groups.get(workspaceId);
}

export async function messages(channelId) {
  return readJson(`/api/product/channel/messages?channel_id=${encodeURIComponent(channelId)}`);
}

// ---- writes ----------------------------------------------------------------

let counter = 0;
const nonce = Math.random().toString(36).slice(2, 10);

export function requestId(prefix) {
  counter += 1;
  return `ui-${prefix}-${counter}-${nonce}`;
}

// Every write goes through here so the page re-reads once afterwards. Writes
// that change a discovery result or a group also drop that cache entry.
export async function write(path, body = {}, {invalidate = {}} = {}) {
  const result = await apiFetch("POST", path, body);
  if (invalidate.discovery) { state.discovery.clear(); state.geo.clear(); }
  if (invalidate.group) state.groups.delete(invalidate.group);
  if (invalidate.groups) state.groups.clear();
  refresh();
  return result;
}

// ---- polling ----------------------------------------------------------------

export function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (document.visibilityState === "visible" && state.phase === "ready") load();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && state.phase === "ready") refresh();
  });
  // Writes made by an assistant through the browser tools (webmcp_live.mjs,
  // collab.mjs, workspaces.mjs) go through session.mjs, which announces them.
  document.addEventListener("resonance:write", (event) => {
    if (event.detail?.path === "/api/product/resonances/seen") return;
    state.discovery.clear();
    state.geo.clear();
    state.groups.clear();
    refresh();
  });
  document.addEventListener("resonance:discovered", () => { state.discovery.clear(); state.geo.clear(); refresh(); });
}

// ---- derived views ---------------------------------------------------------

export function thoughts() {
  return state.overview?.mine?.thoughts || [];
}

export function discoverableThoughts() {
  return thoughts().filter((row) => row.state === "discoverable");
}

export function alerts() {
  return state.overview?.resonances?.alerts || [];
}

export function intros() {
  const box = state.overview?.intros || {};
  return {incoming: box.incoming || [], outgoing: box.outgoing || []};
}

export function connections() {
  const {incoming, outgoing} = intros();
  return [...incoming, ...outgoing].filter((row) => row.state === "accepted" && row.channel_id);
}

export function topics() {
  const box = state.overview?.topics || {};
  return {topics: box.topics || [], invitations: box.invitations || []};
}

export function account() {
  return state.overview?.account || state.stamped || null;
}

// Whether an intro exists with the owner of a matched session, in any state.
export function introFor(sessionId) {
  const {incoming, outgoing} = intros();
  for (const row of outgoing) if (row.to_session_id === sessionId) return row;
  for (const row of incoming) if (row.from_session_id === sessionId) return row;
  return null;
}
