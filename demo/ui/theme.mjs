/*
 * Colour scheme, applied before first paint.
 *
 * Loaded as a plain blocking script in <head> (no import/export, so it can be)
 * so the page never flashes the wrong scheme. The choice is the viewer's own:
 * "light" (the default), "dark", or "system" (follow the OS). It lives in
 * localStorage under one key and is written back by the control in the
 * masthead (shell.mjs). Storage may be empty, blocked or throwing; every path
 * here ends with a valid theme on the root element.
 *
 *   data-theme-choice  what the person chose: light | dark | system
 *   data-theme         what is painted:       light | dark
 */
(function () {
  var KEY = "resonance_theme";
  var CHOICES = {light: true, dark: true, system: true};
  var root = document.documentElement;

  function stored() {
    try {
      var value = localStorage.getItem(KEY);
      return CHOICES[value] ? value : "light";
    } catch (error) {
      return "light";
    }
  }

  function systemPrefersDark() {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch (error) {
      return false;
    }
  }

  function apply(choice) {
    var resolved = choice === "system" ? (systemPrefersDark() ? "dark" : "light") : choice;
    root.setAttribute("data-theme-choice", choice);
    root.setAttribute("data-theme", resolved);
  }

  function choose(choice) {
    if (!CHOICES[choice]) choice = "light";
    try { localStorage.setItem(KEY, choice); } catch (error) { /* private mode: still applied for this view */ }
    apply(choice);
  }

  apply(stored());

  try {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var follow = function () {
      if (root.getAttribute("data-theme-choice") === "system") apply("system");
    };
    if (media.addEventListener) media.addEventListener("change", follow);
    else if (media.addListener) media.addListener(follow);
  } catch (error) { /* no matchMedia: the choice still applies */ }

  window.__resonanceTheme = {
    key: KEY,
    choice: function () { return root.getAttribute("data-theme-choice") || "light"; },
    choose: choose,
  };
})();
