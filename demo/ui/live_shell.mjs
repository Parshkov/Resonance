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
  "Live product. Share a thought from your agent (WebMCP tools) or open the " +
  "Collaboration panel (top bar) to discover people and start an introduction.";

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function markLiveShell() {
  document.body.dataset.resonanceMode = "live";
  setText("thought-id", "Live product · your shared thoughts live in your account");
  setText("thought-caption", LIVE_HINT);
  // With no demo context the page settles in its error state, which shows the
  // evidence panel alone; the hint has to be where the visitor is looking.
  setText("evidence-kicker", "Live product");
  setText("evidence-heading", "Your shared thoughts live in your account");
  setText("evidence-subtitle", LIVE_HINT);
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
  // With no demo context the R9 surfaces stay empty, so the working surface
  // (the collaboration drawer owned by collab_ui.mjs) is opened for the visitor.
  document.dispatchEvent(new CustomEvent("resonance:collab-open"));
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
