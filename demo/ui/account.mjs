// Who you are on this page, and the name other people see you under.
//
// Resonance introduces people whose reasoning has the same shape, so the
// account is the product's subject, not an implementation detail. The
// masthead says two things: that you are signed in, and the pseudonym other
// participants see — never your name or your address, which the server does
// not hand this page at all. Where a deployment offers a sign-in, that is the
// only way in and the page says so in the body. Where it offers none (a local
// run), the pseudonymous account is named for what it is.

const slot = document.getElementById("account-slot");
const gate = document.getElementById("signin-gate");
const gateActions = document.getElementById("gate-actions");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function signInHref(base) {
  const here = window.location.pathname + window.location.search;
  return `${base || "/auth/sign-in"}?next=${encodeURIComponent(here)}`;
}

function signInLink(base, className) {
  const link = element("a", className, "Sign in");
  link.href = signInHref(base);
  return link;
}

function returnThemeHome() {
  // Whoever is looking must be able to reach it. With no account button there
  // is no panel to hold it, so it goes back to where the page keeps it.
  const theme = document.getElementById("theme-switch");
  const home = document.getElementById("theme-home");
  if (theme && home && theme.parentElement !== home) home.append(theme);
}

function renderSignedOut(state, urgent = false) {
  returnThemeHome();
  const link = signInLink(state.sign_in_url, "account-action");
  if (urgent) link.classList.add("account-action-urgent");
  slot.replaceChildren(link);
  if (gate && gateActions) {
    gateActions.replaceChildren(signInLink(state.sign_in_url, "button button-primary"));
    gate.hidden = false;
  }
  document.body.dataset.signedIn = "false";
}

function closePanel() {
  const open = slot.querySelector(".account-panel:not([hidden])");
  if (!open) return;
  open.hidden = true;
  const button = slot.querySelector(".account-button");
  if (button) button.setAttribute("aria-expanded", "false");
}

document.addEventListener("click", (event) => {
  if (slot && !slot.contains(event.target)) closePanel();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closePanel();
});

function renderSignedIn(account) {
  // The masthead used to carry three separate texts -- "Signed in", "Others
  // see you as X", and a Sign out button -- all shouting at the same volume,
  // and none of them answering the question a person actually has: who am I
  // here, and who can see what?
  //
  // One control now. It shows the only identity that matters on this page,
  // the name other people see. Opening it says who you signed in as, what
  // that name is for, and offers the way out. The explanation lives where it
  // is needed instead of permanently in the bar.
  const label = (account.display_label || account.user_id || "").trim();

  const button = element("button", "account-button");
  button.type = "button";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-haspopup", "dialog");
  button.append(element("span", "account-button__mark", initials(label)));
  const naming = element("span", "account-button__naming");
  naming.append(element("span", "account-button__role", "Your name here"));
  naming.append(element("span", "account-button__label", label));
  button.append(naming);

  const panel = element("div", "account-panel");
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Your account");

  const seen = element("div", "account-panel__row");
  seen.append(element("p", "account-panel__caption", "Everyone else sees you as"));
  seen.append(element("p", "account-panel__value", label));
  seen.append(element("p", "account-panel__note",
    "This is the only name anyone here can see. Your real name and your "
    + "address are never shown to another person."));
  panel.append(seen);

  if (account.signed_in && account.sign_in_email) {
    const me = element("div", "account-panel__row");
    me.append(element("p", "account-panel__caption", "You signed in as"));
    me.append(element("p", "account-panel__value", account.sign_in_email));
    me.append(element("p", "account-panel__note",
      "Only you see this. It is how you get back to this account from another "
      + "device or another chat."));
    panel.append(me);
  } else if (!account.signed_in) {
    const local = element("div", "account-panel__row");
    local.append(element("p", "account-panel__caption", "This browser only"));
    local.append(element("p", "account-panel__note",
      "There is no sign-in on this deployment, so this account lives in this "
      + "browser and cannot be reached from another device."));
    panel.append(local);
  }

  // A preference lives behind the account, not across the top of the page.
  // The control itself is moved, not rebuilt, so shell.mjs keeps the one set
  // of listeners it bound at load and there is no second copy to disagree.
  const theme = document.getElementById("theme-switch");
  if (theme) {
    const row = element("div", "account-panel__row");
    row.append(element("p", "account-panel__caption", "Colours"));
    row.append(theme);
    panel.append(row);
  }

  // Sign-out changes state, so it is a POST form rather than a link that a
  // prefetch or a link scanner could follow on the person's behalf.
  const form = element("form", "account-panel__out");
  form.method = "post";
  form.action = "/auth/sign-out";
  const out = element("button", "account-action", "Sign out");
  out.type = "submit";
  form.append(out);
  panel.append(form);

  button.addEventListener("click", () => {
    const showing = panel.hidden;
    panel.hidden = !showing;
    button.setAttribute("aria-expanded", showing ? "true" : "false");
  });

  slot.replaceChildren(button, panel);
  rendered = fingerprint(account);
  if (gate) gate.hidden = true;
  document.body.dataset.signedIn = "true";
}

function initials(label) {
  const words = label.split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  return (words[0][0] + (words[1]?.[0] || "")).toUpperCase();
}

// What the server already told us, in the HTML it served. Rendering from this
// first is what stops the masthead arriving a moment late and shoving the row
// it sits in -- a jump that happened on every single load.
function stampedAccount() {
  if (!slot || !slot.dataset.accountLabel) return null;
  return {
    display_label: slot.dataset.accountLabel,
    sign_in_email: slot.dataset.accountEmail || "",
    signed_in: slot.dataset.accountSignedIn === "true",
    user_id: "",
  };
}

let rendered = null;

function fingerprint(account) {
  return [account.display_label, account.sign_in_email, account.signed_in].join("\u0000");
}

export async function refreshAccount() {
  if (!slot) return;
  let state = null;
  try {
    state = await fetch("/api/product/state", {credentials: "same-origin"})
      .then(r => r.json());
  } catch {
    return;                       // offline: leave the slot as it was
  }
  const account = state?.account || {};
  if (account.user_id && (account.signed_in || !state.sign_in_required)) {
    // Repainting an identical masthead is how a jump gets reintroduced later.
    if (fingerprint(account) !== rendered) renderSignedIn(account);
    return;
  }
  if (state?.sign_in_required) {
    renderSignedOut(state);
    return;
  }
  slot.replaceChildren();
  if (gate) gate.hidden = true;
}

// Paint what the server stamped, immediately, before any request goes out.
const stamped = stampedAccount();
if (stamped) renderSignedIn(stamped);
refreshAccount();
// A share, a revoke or a client authorization can change who the page is
// acting as; re-read rather than trusting the first answer.
document.addEventListener("resonance:write", () => { refreshAccount(); });
// Something was attempted that needs an account. The page does not navigate on
// its own — a reader who has not decided yet keeps the page they are reading —
// so make the way in visible and unmistakable instead.
document.addEventListener("resonance:sign-in-required", (event) => {
  if (!slot) return;
  renderSignedOut({sign_in_url: event.detail?.signInUrl, sign_in_required: true}, true);
});
