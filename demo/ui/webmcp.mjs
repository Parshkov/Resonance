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
  const host = document.querySelector(".system-status") || document.body;
  host.append(node);
  return node;
}

function setStatus(text) {
  statusNode().textContent = text;
}

function executionSignal(options) {
  return options?.signal || undefined;
}

async function jsonFetch(url, options = {}, executionOptions) {
  const response = await fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
    signal: executionSignal(executionOptions),
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
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
  if (state.shared) {
    setStatus("WebMCP · shared");
  } else if (state.draft_ready) {
    setStatus("WebMCP · private draft ready");
  } else {
    setStatus("WebMCP · private");
  }
}

async function readAuthoritativeState() {
  return jsonFetch("/api/webmcp/state");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function reconcileCommitted(operation, requestId) {
  if (!WRITE_OPERATIONS.has(operation) || !requestId) return null;
  const query = new URLSearchParams({operation, request_id: requestId});
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await fetch(`/api/webmcp/operation?${query}`, {
      cache: "no-store",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
    });
    const payload = await response.json();
    if (response.ok && payload.committed === true) return payload.result;
    if (response.status !== 404 || payload.retryable !== true) {
      const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
      error.code = payload.error || "reconcile_failed";
      error.retryable = payload.retryable === true;
      error.status = response.status;
      throw error;
    }
    if (attempt < 2) await sleep(25);
  }
  return null;
}

async function executeWrite(operation, url, payload, options) {
  const requestId = payload.request_id;
  try {
    const result = await jsonFetch(url, {
      method: "POST",
      body: JSON.stringify(payload),
    }, options);
    const state = await readAuthoritativeState();
    applyAuthoritativeState(state);
    return result;
  } catch (error) {
    if (error?.name !== "AbortError") throw error;
    const committed = await reconcileCommitted(operation, requestId);
    if (committed === null) throw error;
    const state = await readAuthoritativeState();
    applyAuthoritativeState(state);
    setStatus(`${statusNode().textContent} · reconciled`);
    return committed;
  }
}

function selectVisibleMatch(sessionId) {
  const selector = `.match-card[data-session-id="${CSS.escape(sessionId)}"]`;
  document.querySelector(selector)?.click();
}

// The page owns the results view; a discovery run through the tools has to
// show up there too, or the visitor is looking at a stale answer.
function announceDiscovery() {
  document.dispatchEvent(new CustomEvent("resonance:discovered"));
}

const REQUEST_ID_PROPERTY = {
  type: "string",
  minLength: 1,
  maxLength: 128,
  pattern: "^[A-Za-z0-9_.:-]+$",
  description: "Stable idempotency key for this logical write. Reuse the same value when retrying the same operation.",
};

const tools = [
  {
    name: "resonance_prepare_thought",
    title: "Prepare current thought for sharing",
    description: "Create a private, non-discoverable draft from the current Resonance thought. This does not share or index it. Supply a stable request_id and reuse it if the tool call is retried.",
    inputSchema: {
      type: "object",
      required: ["request_id"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        note: {type: "string", maxLength: 500, description: "Optional private note describing the draft."},
      },
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input, options) => executeWrite("prepare", "/api/webmcp/prepare", {
      request_id: input?.request_id || "",
      note: input?.note || "",
    }, options),
  },
  {
    name: "resonance_get_share_preview",
    title: "Preview prepared Resonance share",
    description: "Read the exact structured fields that would become discoverable and obtain the one-time confirmation token required by the explicit share tool.",
    inputSchema: {type: "object", properties: {}, additionalProperties: false},
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (_input, options) => jsonFetch("/api/webmcp/preview", {}, options),
  },
  {
    name: "resonance_share_prepared_thought",
    title: "Share prepared thought with Resonance",
    description: "Explicitly share the prepared draft after preview. Requires confirm=true, the preview confirmation_token, and a stable request_id that must be reused on retry.",
    inputSchema: {
      type: "object",
      required: ["request_id", "confirm", "confirmation_token"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        confirm: {type: "boolean", description: "Must be true after the human has reviewed the share preview."},
        confirmation_token: {type: "string", minLength: 1, maxLength: 256, description: "Opaque token returned only by resonance_get_share_preview."},
      },
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input, options) => executeWrite("share", "/api/webmcp/share", {
      request_id: input?.request_id || "",
      confirm: input?.confirm === true,
      confirmation_token: input?.confirmation_token || "",
    }, options),
  },
  {
    name: "resonance_discover",
    title: "Discover structural resonance",
    description: "Run structural discovery for the currently shared thought. Returns a result_id that binds later evidence reads to this exact discovery payload.",
    inputSchema: {type: "object", properties: {}, additionalProperties: false},
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (input, options) => {
      const result = await jsonFetch("/api/webmcp/discover", {}, options);
      announceDiscovery();
      setStatus("WebMCP · discovery run");
      return result;
    },
  },
  {
    name: "resonance_get_match",
    title: "Get evidence for a Resonance match",
    description: "Return backend evidence for one discoverable match from the exact discovery result identified by result_id.",
    inputSchema: {
      type: "object",
      required: ["result_id", "session_id"],
      properties: {
        result_id: {type: "string", pattern: "^result-[0-9a-f]{24}$", description: "Opaque result_id returned by resonance_discover."},
        session_id: {type: "string", minLength: 1, maxLength: 128},
      },
      additionalProperties: false,
    },
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (input, options) => {
      const resultId = input?.result_id || "";
      const sessionId = input?.session_id || "";
      const query = new URLSearchParams({result_id: resultId, session_id: sessionId});
      const result = await jsonFetch(`/api/webmcp/match?${query}`, {}, options);
      selectVisibleMatch(sessionId);
      setStatus("WebMCP · evidence opened");
      return result;
    },
  },
  {
    name: "resonance_update_consent",
    title: "Revoke Resonance discovery consent",
    description: "Revoke discoverability for the current thought. Supply a stable request_id and reuse it on retry. Revocation also invalidates retained discovery result ids. Restoring sharing requires prepare, preview, and explicit share.",
    inputSchema: {
      type: "object",
      required: ["request_id", "shared"],
      properties: {
        request_id: REQUEST_ID_PROPERTY,
        shared: {type: "boolean", description: "Set false to revoke discovery sharing. true is only accepted when sharing is already enabled."},
      },
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input, options) => executeWrite("consent", "/api/webmcp/consent", {
      request_id: input?.request_id || "",
      shared: input?.shared === true,
    }, options),
  },
];

async function registerWebMCP() {
  // document.modelContext is the current WebMCP surface. Chromium builds from
  // the transition period expose the same native object only on navigator.
  const modelContext = document.modelContext || navigator.modelContext;
  if (!modelContext?.registerTool) {
    setStatus("WebMCP · unavailable");
    return false;
  }
  try {
    for (const tool of tools) {
      await modelContext.registerTool(tool, {signal: registrationController.signal});
    }
    setStatus(`WebMCP · ${tools.length} tools`);
    return true;
  } catch (error) {
    registrationController.abort();
    setStatus("WebMCP · registration failed");
    console.error("Resonance WebMCP registration failed", error);
    return false;
  }
}

export {
  TOOL_NAMES,
  WEBMCP_CONTRACT,
  executeWrite,
  reconcileCommitted,
  registerWebMCP,
  tools,
};

window.__resonanceWebMCP = {contract: WEBMCP_CONTRACT, toolNames: TOOL_NAMES};
void registerWebMCP();
