/**
 * R14 committed session/CSRF bootstrap (fixes the reviewer's CSRF gap).
 *
 * The session cookie is HttpOnly, so JS cannot read it, and the CSRF token is
 * revealed only at issue time. This module makes a usable CSRF token available
 * to the collaboration surfaces after a reload with an owned session, with no
 * test-harness secret injection:
 *
 *   - persist the CSRF token in sessionStorage at issue time (per-tab, survives
 *     reload);
 *   - on load, if the cookie authenticates a session but sessionStorage has no
 *     token (e.g. a fresh tab), call POST /api/product/rotate to mint a fresh
 *     CSRF for the SAME subject and store it;
 *   - if there is no session at all, create a guest and store its token.
 *
 * Everything is same-origin and cookie-scoped; the stored value is only the
 * double-submit CSRF token, never the access cookie.
 */

const CSRF_KEY = "resonance_csrf";
const USER_KEY = "resonance_user";

function readStored(key) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}

function writeStored(key, value) {
  try { sessionStorage.setItem(key, value); } catch { /* private mode */ }
}

function rememberCredentials(creds) {
  if (creds?.csrf_token) writeStored(CSRF_KEY, creds.csrf_token);
  if (creds?.user_id) writeStored(USER_KEY, creds.user_id);
  window.__resonance_csrf = creds?.csrf_token || window.__resonance_csrf;
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

async function ensureSession() {
  const cached = readStored(CSRF_KEY);
  if (cached) {
    window.__resonance_csrf = cached;
    return cached;
  }
  if (bootstrapPromise) return bootstrapPromise;
  bootstrapPromise = (async () => {
    const state = await currentState();
    const authenticated = !!(state && state.owned_sessions);
    if (authenticated) {
      // Owned session survived (cookie present) but the CSRF value is not in
      // this tab — mint a fresh one for the same subject.
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
  })();
  return bootstrapPromise;
}

function getCsrf() {
  return readStored(CSRF_KEY) || window.__resonance_csrf || null;
}

async function apiFetch(method, path, body) {
  const csrf = await ensureSession();
  const headers = {"Content-Type": "application/json"};
  if (csrf) headers["X-Resonance-CSRF"] = csrf;
  const response = await fetch(path, {
    method, credentials: "same-origin", headers,
    body: method === "POST" ? JSON.stringify(body || {}) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`${payload.error || response.status}: ${payload.message || "request failed"}`);
  }
  return payload;
}

// Establish a session as soon as the page loads so tools/UI are ready.
ensureSession();

export { CSRF_KEY, apiFetch, ensureSession, getCsrf, rememberCredentials };
