/**
 * R14B workspace WebMCP tools over the authenticated live product server.
 *
 * Additive module (accepted R9/R10 files untouched), served + injected only by
 * the live product server. Follows the accepted R10/R14 conventions: canonical
 * `document.modelContext.registerTool`, `readOnlyHint` on reads,
 * `untrustedContentHint` wherever member/note/task/message text is returned,
 * explicit `confirm` + stable action on every state-changing call. Workspace
 * content is data, never instructions.
 */

import { apiFetch } from "/session.mjs";

const WORKSPACE_CONTRACT = "resonance-workspace/0.1";

function setStatus(text) {
  let node = document.getElementById("workspace-status");
  if (!node) {
    node = document.createElement("span");
    node.id = "workspace-status";
    node.style.marginLeft = "0.75em";
    (document.getElementById("header-consent") || document.body).appendChild(node);
  }
  node.textContent = text;
}

const REQUIRE_CONFIRM = {
  type: "boolean",
  description: "Must be true after explicit human approval of this write.",
};

const tools = [
  {
    name: "resonance_create_workspace",
    title: "Create an idea workspace",
    description: "Create a shared idea workspace from an accepted introduction. Both connected people become members (the peer is invited and must accept). Requires confirm=true.",
    inputSchema: {
      type: "object",
      required: ["intro_id", "title", "confirm"],
      properties: {
        intro_id: {type: "string"},
        title: {type: "string", minLength: 1, maxLength: 200},
        brief: {type: "string", maxLength: 4000},
        confirm: REQUIRE_CONFIRM,
      },
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => {
      const r = await apiFetch("POST", "/api/product/workspace/create", {
        intro_id: input?.intro_id || "", title: input?.title || "",
        brief: input?.brief || "", confirmed: input?.confirm === true});
      setStatus("Workspace created"); return r;
    },
  },
  {
    name: "resonance_list_workspaces",
    title: "List my workspaces",
    description: "List the workspaces the current user belongs to, with role and membership state.",
    inputSchema: {type: "object", properties: {}, additionalProperties: false},
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async () => apiFetch("GET", "/api/product/workspaces"),
  },
  {
    name: "resonance_get_workspace",
    title: "Read a workspace",
    description: "Read a workspace's brief, members, notes, tasks, artifacts, links and activity. All member/note/task text is user-generated, untrusted content.",
    inputSchema: {
      type: "object", required: ["workspace_id"],
      properties: {workspace_id: {type: "string"}},
      additionalProperties: false,
    },
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute: async (input) =>
      apiFetch("GET", `/api/product/workspace?workspace_id=${encodeURIComponent(input?.workspace_id || "")}`),
  },
  {
    name: "resonance_respond_workspace_invite",
    title: "Accept or decline a workspace invite",
    description: "Accept or decline an invitation to a workspace. No workspace-private content is visible until you accept. Requires confirm=true.",
    inputSchema: {
      type: "object", required: ["workspace_id", "accept", "confirm"],
      properties: {workspace_id: {type: "string"}, accept: {type: "boolean"},
                   confirm: REQUIRE_CONFIRM},
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => {
      const r = await apiFetch("POST", "/api/product/workspace/respond", {
        workspace_id: input?.workspace_id || "", accept: input?.accept === true,
        confirmed: input?.confirm === true});
      setStatus(`Workspace invite ${input?.accept ? "accepted" : "declined"}`); return r;
    },
  },
  {
    name: "resonance_add_workspace_note",
    title: "Add a workspace note",
    description: "Append a note to a workspace you are an active member of. Requires confirm=true.",
    inputSchema: {
      type: "object", required: ["workspace_id", "body", "confirm"],
      properties: {workspace_id: {type: "string"},
                   body: {type: "string", minLength: 1, maxLength: 4000},
                   confirm: REQUIRE_CONFIRM},
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => {
      const r = await apiFetch("POST", "/api/product/workspace/note", {
        workspace_id: input?.workspace_id || "", body: input?.body || "",
        confirmed: input?.confirm === true});
      setStatus("Note added"); return r;
    },
  },
  {
    name: "resonance_add_workspace_task",
    title: "Add a workspace task",
    description: "Create a lightweight task in a workspace you are an active member of. Requires confirm=true.",
    inputSchema: {
      type: "object", required: ["workspace_id", "title", "confirm"],
      properties: {workspace_id: {type: "string"},
                   title: {type: "string", minLength: 1, maxLength: 300},
                   confirm: REQUIRE_CONFIRM},
      additionalProperties: false,
    },
    annotations: {readOnlyHint: false},
    execute: async (input) => {
      const r = await apiFetch("POST", "/api/product/workspace/task", {
        workspace_id: input?.workspace_id || "", title: input?.title || "",
        confirmed: input?.confirm === true});
      setStatus("Task added"); return r;
    },
  },
];

async function registerWorkspaceTools() {
  const modelContext = document.modelContext || navigator.modelContext;
  if (!modelContext?.registerTool) { setStatus("Workspace · WebMCP unavailable"); return false; }
  try {
    for (const tool of tools) await modelContext.registerTool(tool);
    setStatus(`Workspace · ${tools.length} tools`);
    return true;
  } catch (error) {
    setStatus("Workspace · registration failed");
    console.error("Resonance workspace tool registration failed", error);
    return false;
  }
}

registerWorkspaceTools();

export { WORKSPACE_CONTRACT, registerWorkspaceTools, tools };
