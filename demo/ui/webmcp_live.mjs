/**
 * Competition LIVE WebMCP transport.
 *
 * Same accepted R10 tool names and concise schemas, but all reads/writes go to
 * the authenticated LiveProductService through src.product.competition_server.
 * session.mjs supplies the real cookie-bound CSRF proof; there is no browser
 * shadow corpus or matching logic here.
 */

import { apiFetch, ensureSession } from "/session.mjs";

const WEBMCP_CONTRACT = "resonance-webmcp/0.1";
const TOOL_NAMES = [
  "resonance_prepare_thought",
  "resonance_get_share_preview",
  "resonance_share_prepared_thought",
  "resonance_discover",
  "resonance_get_match",
  "resonance_update_consent",
];

const registrationController = new AbortController();
const WRITE_OPERATIONS = new Set(["prepare", "share", "consent"]);

function statusNode() {
  let node = document.getElementById("webmcp-status");
  if (node) return node;
  node = document.createElement("span");
  node.id = "webmcp-status";
  node.className = "offline-badge";
  node.setAttribute("role", "status");
  node.textContent = "WebMCP · checking";
  (document.querySelector(".system-status") || document.body).append(node);
  return node;
}

function setStatus(text) { statusNode().textContent = text; }

async function readJson(url, options = {}) {
  await ensureSession();
  const response = await fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
    error.code = payload.error || "http_error";
    error.retryable = payload.retryable === true;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function setConsentVisible(shared) {
  const host = document.getElementById("header-consent");
  if (!host) return;
  host.replaceChildren();
  const light = document.createElement("span");
  light.className = "status-light";
  const copy = document.createElement("span");
  copy.textContent = shared ? "Shared with Resonance" : "Private · not discoverable";
  host.append(light, copy);
  host.dataset.shared = String(shared);
}

function applyAuthoritativeState(state) {
  setConsentVisible(state.shared === true);
  if (state.shared) setStatus("WebMCP · LIVE shared");
  else if (state.draft_ready) setStatus("WebMCP · private draft ready");
  else setStatus("WebMCP · private");
}

async function readAuthoritativeState() {
  return readJson("/api/webmcp/state");
}

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function reconcileCommitted(operation, requestId) {
  if (!WRITE_OPERATIONS.has(operation) || !requestId) return null;
  const query = new URLSearchParams({operation, request_id: requestId});
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await fetch(`/api/webmcp/operation?${query}`, {
      cache: "no-store", credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.committed === true) return payload.result;
    if (response.status !== 404 || payload.retryable !== true) {
      const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
      error.code = payload.error || "reconcile_failed";
      throw error;
    }
    if (attempt < 2) await sleep(25);
  }
  return null;
}

async function executeWrite(operation, url, payload) {
  try {
    const result = await apiFetch("POST", url, payload);
    applyAuthoritativeState(await readAuthoritativeState());
    return result;
  } catch (error) {
    if (error?.name !== "AbortError") throw error;
    const committed = await reconcileCommitted(operation, payload.request_id);
    if (committed === null) throw error;
    applyAuthoritativeState(await readAuthoritativeState());
    setStatus(`${statusNode().textContent} · reconciled`);
    return committed;
  }
}

function selectVisibleMatch(sessionId) {
  const selector = `.match-card[data-session-id="${CSS.escape(sessionId)}"]`;
  document.querySelector(selector)?.click();
}

function activateLiveDiscovery() {
  document.getElementById("source-live")?.click();
}

const REQUEST_ID_PROPERTY = {
  type: "string", minLength: 1, maxLength: 128,
  pattern: "^[A-Za-z0-9_.:-]+$",
  description: "Stable idempotency key. Reuse it when retrying the same logical write.",
};

const tools = [
  {
    name: "resonance_prepare_thought",
    title: "Prepare the person's thought for sharing",
    description: "Create a private durable draft of the person's REAL reasoning: pass `thought` (a labelled causal graph you extracted from the conversation — preferred) or `context` (raw text, ≤ 4000 chars, for the deterministic cue extractor). Without either, the thought currently visible on the page is used. The text is never retained; nothing becomes discoverable yet.",
    inputSchema: {
      type: "object", required: ["request_id"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        note: {type: "string", maxLength: 500, description: "Optional private preparation note."},
        thought: {
          type: "object", required: ["nodes", "relations"],
          description: "Causal structure of what the person is working on. Labels are short noun phrases (no sentences, no personal data).",
          properties: {
            topic: {type: "string", maxLength: 120, description: "3-8 word public title."},
            domain: {type: "string", maxLength: 60, description: "Field, e.g. 'distributed-systems'."},
            nodes: {
              type: "array", minItems: 2, maxItems: 24,
              items: {type: "object", required: ["label", "role"], additionalProperties: false,
                      properties: {id: {type: "string", maxLength: 32}, label: {type: "string", maxLength: 120},
                                   role: {type: "string", enum: ["agent", "constraint", "evidence", "mechanism", "method", "outcome", "problem", "resource", "state"]},
                                   negated: {type: "boolean"},
                                   modality: {type: "string", enum: ["actual", "possible", "conditional"]}}},
            },
            relations: {
              type: "array", minItems: 1, maxItems: 48,
              items: {type: "object", required: ["source", "target", "type"], additionalProperties: false,
                      properties: {source: {type: "string", description: "node id or label"},
                                   target: {type: "string", description: "node id or label"},
                                   type: {type: "string", enum: ["causes", "constrains", "contradicts", "part_of", "prevents", "requires", "supports"]},
                                   negated: {type: "boolean"},
                                   modality: {type: "string", enum: ["actual", "possible", "conditional"]}}},
            },
          }, additionalProperties: false,
        },
        context: {type: "string", maxLength: 4000, description: "Raw text fallback when a graph cannot be extracted."},
      }, additionalProperties: false,
    },
    annotations: {readOnlyHint: false, untrustedContentHint: true},
    execute: async (input) => {
      const payload = {request_id: input?.request_id || "", note: input?.note || ""};
      if (input?.thought !== undefined) payload.thought = input.thought;
      if (input?.context) payload.context = input.context;
      return executeWrite("prepare", "/api/webmcp/prepare", payload);
    },
  },
  {
    name: "resonance_get_share_preview",
    title: "Preview prepared Resonance share",
    description: "Read the exact structured fields that would become discoverable and obtain the one-time confirmation token.",
    inputSchema: {type: "object", properties: {}, additionalProperties: false},
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async () => readJson("/api/webmcp/preview"),
  },
  {
    name: "resonance_share_prepared_thought",
    title: "Share prepared thought with Resonance",
    description: "Explicitly publish the prepared Thought DNA after preview. Requires confirm=true and the preview token.",
    inputSchema: {
      type: "object", required: ["request_id", "confirm", "confirmation_token"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        confirm: {type: "boolean", description: "Must be true after the human reviews the preview."},
        confirmation_token: {type: "string", minLength: 1, maxLength: 256},
      }, additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => executeWrite("share", "/api/webmcp/share", {
      request_id: input?.request_id || "",
      confirm: input?.confirm === true,
      confirmation_token: input?.confirmation_token || "",
    }),
  },
  {
    name: "resonance_discover",
    title: "Discover structural resonance",
    description: "Run DB-backed structural discovery for the currently shared live session. Replay is explicitly labelled and never a silent fallback.",
    inputSchema: {
      type: "object",
      properties: {source: {type: "string", enum: ["live", "replay"], default: "live"}},
      additionalProperties: false,
    },
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (input) => {
      const source = input?.source === "replay" ? "replay" : "live";
      const result = await readJson(`/api/webmcp/discover?source=${encodeURIComponent(source)}`);
      if (source === "live") activateLiveDiscovery();
      setStatus(`WebMCP · ${source === "live" ? "LIVE DB" : "REPLAY"} discovery`);
      return result;
    },
  },
  {
    name: "resonance_get_match",
    title: "Get evidence for a Resonance match",
    description: "Read evidence bound to one exact discovery result_id and session_id; never silently switches sources.",
    inputSchema: {
      type: "object", required: ["result_id", "session_id"],
      properties: {
        result_id: {type: "string", pattern: "^result-[0-9a-f]{24}$"},
        session_id: {type: "string", minLength: 1, maxLength: 128},
      }, additionalProperties: false,
    },
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (input) => {
      const query = new URLSearchParams({
        result_id: input?.result_id || "", session_id: input?.session_id || "",
      });
      const result = await readJson(`/api/webmcp/match?${query}`);
      selectVisibleMatch(input?.session_id || "");
      setStatus(`WebMCP · ${result.source} evidence opened`);
      return result;
    },
  },
  {
    name: "resonance_update_consent",
    title: "Revoke Resonance discovery consent",
    description: "Set shared=false to revoke the current live session. Re-sharing requires prepare, preview, and explicit share again.",
    inputSchema: {
      type: "object", required: ["request_id", "shared"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        shared: {type: "boolean"},
      }, additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => executeWrite("consent", "/api/webmcp/consent", {
      request_id: input?.request_id || "", shared: input?.shared === true,
    }),
  },
];

async function registerWebMCP() {
  const modelContext = document.modelContext || navigator.modelContext;
  if (!modelContext?.registerTool) {
    setStatus("WebMCP · unavailable");
    // No agent surface in this browser, but the header must still tell the
    // truth about the visitor's own consent state (private by default).
    try {
      await ensureSession();
      applyAuthoritativeState(await readAuthoritativeState());
    } catch (error) {
      console.warn("Resonance consent state unavailable", error);
    }
    return false;
  }
  try {
    await ensureSession();
    for (const tool of tools) {
      await modelContext.registerTool(tool, {signal: registrationController.signal});
    }
    applyAuthoritativeState(await readAuthoritativeState());
    return true;
  } catch (error) {
    registrationController.abort();
    setStatus("WebMCP · registration failed");
    console.error("Resonance LIVE WebMCP registration failed", error);
    return false;
  }
}

export {
  TOOL_NAMES, WEBMCP_CONTRACT, executeWrite, reconcileCommitted,
  registerWebMCP, tools,
};

window.__resonanceWebMCP = {
  contract: WEBMCP_CONTRACT, toolNames: TOOL_NAMES, mode: "live-product",
};
void registerWebMCP();
