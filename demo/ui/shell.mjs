/**
 * The frame around the page: the colour-scheme control, the navigation, and
 * one place for notices.
 *
 * The navigation is built from the sections that are actually on the page,
 * so it can never offer a destination that does not exist. A section says
 * how it wants to be named with `data-nav-label`, and how many things it is
 * holding with `data-nav-count`; hiding or unhiding a section, a change of
 * the shell state, or a change of count rebuilds the list.
 *
 * Nothing here reads product state; the modules that own a section announce
 * it through the DOM and this reflects it.
 */

const shell = document.getElementById("app-shell");
const main = document.getElementById("main-workspace");
const nav = document.getElementById("page-nav");
const notice = document.getElementById("notice");
const toast = document.getElementById("toast");

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of [].concat(children)) {
    node.append(child?.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

// ---- colour scheme ------------------------------------------------------
//
// theme.mjs applied the stored choice before paint; this control shows it
// and writes a new one. It is the only writer of the preference.

function wireTheme() {
  const control = document.getElementById("theme-switch");
  if (!control) return;
  const api = window.__resonanceTheme;
  const current = api?.choice?.() || document.documentElement.getAttribute("data-theme-choice") || "light";
  for (const input of control.querySelectorAll("input[name=theme]")) {
    input.checked = input.value === current;
    input.addEventListener("change", () => {
      if (!input.checked) return;
      if (api?.choose) api.choose(input.value);
      else document.documentElement.setAttribute("data-theme", input.value === "dark" ? "dark" : "light");
    });
  }
}

// ---- navigation ---------------------------------------------------------

// On the page means rendered: neither the hidden attribute nor a shell-state
// rule in the stylesheet is keeping it off screen.
function presentSections() {
  if (!main) return [];
  return [...main.querySelectorAll(":scope > section[data-nav-label]")]
    .filter((section) => !section.hidden && section.getClientRects().length > 0);
}

let observer = null;
let current = null;

function markCurrent(id) {
  current = id;
  if (!nav) return;
  for (const link of nav.querySelectorAll("a")) {
    if (link.getAttribute("href") === `#${id}`) link.setAttribute("aria-current", "true");
    else link.removeAttribute("aria-current");
  }
}

function watchCurrent(present) {
  if (observer) observer.disconnect();
  if (!("IntersectionObserver" in window)) return;
  observer = new IntersectionObserver((entries) => {
    const visible = new Set(entries.filter((e) => e.isIntersecting).map((e) => e.target.id));
    // The first section in document order that is in the reading band.
    const first = present.find((section) => visible.has(section.id));
    if (first) markCurrent(first.id);
  }, {rootMargin: "-15% 0px -65% 0px", threshold: 0});
  for (const section of present) observer.observe(section);
}

function buildNav() {
  if (!nav) return;
  const present = presentSections();
  nav.replaceChildren();
  nav.hidden = present.length < 2;
  for (const section of present) {
    const link = el("a", {href: `#${section.id}`, className: "page-nav__link"});
    link.append(el("span", {textContent: section.dataset.navLabel}));
    const count = Number(section.dataset.navCount || 0);
    if (count > 0) link.append(el("span", {className: "nav-badge", textContent: String(count)}));
    if (section.id === current) link.setAttribute("aria-current", "true");
    link.addEventListener("click", (event) => {
      // Scroll so the target lands below the sticky masthead, then move
      // focus there so keyboard and screen-reader users arrive too.
      event.preventDefault();
      section.scrollIntoView({block: "start"});
      if (!section.hasAttribute("tabindex")) section.setAttribute("tabindex", "-1");
      section.focus({preventScroll: true});
      history.replaceState(null, "", `#${section.id}`);
      markCurrent(section.id);
    });
    nav.append(link);
  }
  watchCurrent(present);
}

function watchSections() {
  if (!main) return;
  let timer = null;
  const schedule = () => { clearTimeout(timer); timer = setTimeout(buildNav, 80); };
  new MutationObserver(schedule).observe(main, {
    attributes: true, attributeFilter: ["hidden", "data-nav-count"], childList: true,
  });
  if (shell) {
    new MutationObserver(schedule).observe(shell, {attributes: true, attributeFilter: ["data-state"]});
  }
  window.addEventListener("resize", schedule);
  schedule();
}

// ---- notices ------------------------------------------------------------
//
// Modules say what went wrong with one event; the page shows it in one place,
// under the masthead, and clears it on the next successful write.

function showNotice(message) {
  if (!notice) return;
  if (!message) { notice.hidden = true; notice.replaceChildren(); return; }
  const close = el("button", {type: "button", className: "notice-close", textContent: "Dismiss"});
  close.addEventListener("click", () => showNotice(""));
  notice.replaceChildren(el("span", {className: "notice-text", textContent: message}), close);
  notice.hidden = false;
}

let toastTimer = null;
function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2200);
}

document.addEventListener("resonance:notice", (event) => showNotice(event.detail?.message || ""));
document.addEventListener("resonance:toast", (event) => showToast(event.detail?.message || ""));
document.addEventListener("resonance:write", () => showNotice(""));

function init() {
  wireTheme();
  watchSections();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

export { buildNav, showNotice, showToast };
