/**
 * Live-origin shell state (R13 page integration, #88).
 *
 * The accepted R9 page (`app.mjs`) boots from `/api/config` + `/api/context`,
 * which only the R9 demo server provides. On the live product origin those
 * routes do not exist, `boot()` throws, and the page used to sit on its loading
 * placeholders forever ("Loading accepted context…", "Preparing the shared
 * Thought DNA."). This additive module — served and injected only by the live
 * server, accepted R9 files untouched — detects that case and moves the page
 * to an explicit, terminal state that points a human at the surfaces that do
 * work on this origin: the Collaboration panel and the WebMCP tools.
 *
 * No inline script (the live CSP is `default-src 'self'`), no innerHTML.
 */

const LIVE_HINT =
  "Live product. Share a thought from your agent (WebMCP tools) or use the " +
  "Collaboration panel below to discover people and start an introduction.";

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function markLiveShell() {
  document.body.dataset.resonanceMode = "live";
  setText("thought-id", "Live product · your shared thoughts live in your account");
  setText("thought-caption", LIVE_HINT);
  setText("contradiction-topic", "Evidence appears here after a discovery through your agent.");
  setText("source-note", "Live product · discovery runs on your authenticated session");
  const consent = document.getElementById("header-consent");
  if (consent) {
    // The status pill holds an icon span plus the label span; replace the
    // label wherever it sits rather than assuming it is first.
    let replaced = false;
    for (const span of consent.querySelectorAll("span")) {
      if (/checking consent/i.test(span.textContent || "")) {
        span.textContent = "Live product";
        replaced = true;
      }
    }
    if (!replaced) consent.textContent = "Live product";
  }
  // The replay/live source switch is an R9 demo affordance with no backend here.
  for (const button of document.querySelectorAll(".source-option")) {
    button.disabled = true;
    button.setAttribute("aria-disabled", "true");
    button.title = "Source switching is a demo-server feature; this origin is always live.";
  }
  // Bring the working surface into view once the collaboration panel exists.
  const panel = document.getElementById("collab-panel");
  const workspace = document.getElementById("main-workspace");
  if (panel && workspace && panel.parentElement === workspace) {
    workspace.prepend(panel);
  }
}

async function detectAndApply() {
  let demoContextAvailable = false;
  try {
    const response = await fetch("/api/config", {cache: "no-store", credentials: "same-origin"});
    demoContextAvailable = response.ok;
  } catch {
    demoContextAvailable = false;
  }
  if (demoContextAvailable) return false; // R9 demo server: leave the page alone.
  markLiveShell();
  return true;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => { detectAndApply(); });
} else {
  detectAndApply();
}

export { detectAndApply, markLiveShell };
