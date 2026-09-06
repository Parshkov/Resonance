/**
 * The browser WebMCP surface: the remote MCP server's tools, in the browser.
 *
 * A browser that exposes `document.modelContext` (Chrome with WebMCP) lets an
 * agent living in the browser call tools the page registers. This module
 * registers exactly the tools the remote MCP server publishes -- it reads the
 * list from /api/product/tools and executes each through /api/product/tool
 * under the page's own cookie session -- so an agent in a chat and an agent
 * in the browser speak one vocabulary and reach one implementation.
 *
 * There used to be three modules here with a second set of tool names the
 * chat never had. Nothing here matches, ranks or rescores.
 */

import { apiFetch, ensureSession } from "/session.mjs";

const registrationController = new AbortController();

function statusNode() {
  let node = document.getElementById("webmcp-status");
  if (node) return node;
  node = document.createElement("span");
  node.id = "webmcp-status";
  node.setAttribute("role", "status");
  (document.getElementById("tool-status") || document.body).append(node);
  return node;
}

function setStatus(text) { statusNode().textContent = text; }

async function listTools() {
  await ensureSession();
  const response = await fetch("/api/product/tools", {cache: "no-store", credentials: "same-origin"});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  return payload.tools || [];
}

// One tool call. The server answers with the same content blocks the chat
// gets: the result said in words first, then the structured result.
async function callTool(name, input) {
  const answer = await apiFetch("POST", "/api/product/tool", {name, arguments: input || {}});
  if (answer?.isError) {
    const error = new Error(answer.structuredContent?.message || "the tool refused");
    error.code = answer.structuredContent?.error;
    throw error;
  }
  return answer;
}

export async function registerBrowserTools() {
  const modelContext = document.modelContext || navigator.modelContext;
  if (!modelContext?.registerTool) {
    setStatus("WebMCP · unavailable");
    return false;
  }
  let tools;
  try {
    tools = await listTools();
  } catch (error) {
    setStatus(`WebMCP · ${error.message}`);
    return false;
  }
  for (const tool of tools) {
    await modelContext.registerTool({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
      annotations: tool.annotations,
      execute: (input) => callTool(tool.name, input),
    }, {signal: registrationController.signal});
  }
  setStatus(`WebMCP · ${tools.length} tools`);
  return true;
}

if (typeof document !== "undefined") {
  registerBrowserTools().catch((error) => setStatus(`WebMCP · ${error.message}`));
  window.addEventListener("pagehide", () => registrationController.abort());
}
