/**
 * R14 committed session/CSRF bootstrap.
 *
 * The session cookie is HttpOnly and the CSRF token is revealed only at issue
 * time, so a page reload (or a second tab) has no way to read the token back
 * from the cookie. This module makes one usable CSRF token available to every
 * collaboration surface — after reload AND across concurrent tabs of the same
 * subject — with no test-harness secret injection:
 *
 *   - the CSRF token is kept in localStorage, which is shared across all tabs
 *     of the origin, so concurrent tabs reuse ONE token bound to ONE cookie
 *     session instead of each rotating and revoking the others (F4);
 *   - on load, if localStorage already holds a token, it is used as-is (no
 *     rotate, no revocation cascade);
 *   - otherwise, if the cookie authenticates a session, POST /api/product/rotate
 *     mints a fresh token for the SAME subject and stores it;
 *   - if there is no session at all, a guest is created and stored;
 *   - any write that still comes back csrf_rejected clears the stored token and
 *     re-bootstraps once before failing, so a token invalidated by another
 *     client self-heals instead of silently breaking writes.
 *
 * Only the double-submit CSRF token is stored; never the access cookie.
 */

const CSRF_KEY = "resonance_csrf";
const USER_KEY = "resonance_user";

function readStored(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeStored(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode */ }
}

function clearStored(key) {
  try { localStorage.removeItem(key); } catch { /* private mode */ }
}

function rememberCredentials(creds) {
  if (creds?.csrf_token) writeStored(CSRF_KEY, creds.csrf_token);
  if (creds?.user_id) writeStored(USER_KEY, creds.user_id);
  return creds;
}

async function currentState() {
  try {
    return await fetch("/api/product/state", {credentials: "same-origin"})
      .then(r => r.json());
  } catch {
    return null;
  }
}

let bootstrapPromise = null;

async function bootstrap() {
  const cached = readStored(CSRF_KEY);
  if (cached) return cached;
  const state = await currentState();
  // Branch on the explicit authenticated flag, never on owned_sessions length:
  // a registered user who has not shared yet must NOT have a guest silently
  // created for them by a tool/UI call (F2). Only a genuinely unauthenticated
  // visitor gets a fresh guest.
  if (state && state.authenticated) {
    const rotated = await fetch("/api/product/rotate", {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type": "application/json"}, body: "{}",
    });
    if (rotated.ok) return rememberCredentials(await rotated.json()).csrf_token;
  }
  const guest = await fetch("/api/product/guest", {
    method: "POST", credentials: "same-origin",
    headers: {"Content-Type": "application/json"}, body: "{}",
  }).then(r => r.json());
  return rememberCredentials(guest).csrf_token;
}

async function ensureSession({ force = false } = {}) {
  if (force) { clearStored(CSRF_KEY); bootstrapPromise = null; }
  if (!force) {
    const cached = readStored(CSRF_KEY);
    if (cached) return cached;
  }
  if (!bootstrapPromise) bootstrapPromise = bootstrap().finally(() => {
    bootstrapPromise = null;
  });
  return bootstrapPromise;
}

function getCsrf() {
  return readStored(CSRF_KEY);
}

async function apiFetch(method, path, body, { _retried = false } = {}) {
  const csrf = await ensureSession();
  const headers = {"Content-Type": "application/json"};
  if (csrf) headers["X-Resonance-CSRF"] = csrf;
  const response = await fetch(path, {
    method, credentials: "same-origin", headers,
    body: method === "POST" ? JSON.stringify(body || {}) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    // A token invalidated by another client (rotation elsewhere, expiry) shows
    // up as csrf_rejected; re-bootstrap once and retry before surfacing it.
    if (response.status === 403 && payload.error === "csrf_rejected" && !_retried) {
      await ensureSession({ force: true });
      return apiFetch(method, path, body, { _retried: true });
    }
    throw new Error(`${payload.error || response.status}: ${payload.message || "request failed"}`);
  }
  if (method === "POST" && typeof document !== "undefined") {
    // Let on-page surfaces (collaboration panel, status pills) re-read the
    // authorized record after any successful write, whichever client made it
    // (WebMCP tool, workspace tool, or the panel itself).
    document.dispatchEvent(new CustomEvent("resonance:write", {detail: {path}}));
  }
  return payload;
}

// Establish a session as soon as the page loads so tools/UI are ready.
ensureSession();

export { CSRF_KEY, apiFetch, ensureSession, getCsrf, rememberCredentials };
