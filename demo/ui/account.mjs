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

function renderSignedOut(state, urgent = false) {
  const link = signInLink(state.sign_in_url, "account-action");
  if (urgent) link.classList.add("account-action-urgent");
  slot.replaceChildren(link);
  if (gate && gateActions) {
    gateActions.replaceChildren(signInLink(state.sign_in_url, "button button-primary"));
    gate.hidden = false;
  }
  document.body.dataset.signedIn = "false";
}

function renderSignedIn(account) {
  const label = (account.display_label || account.user_id || "").trim();
  const who = element("div", "account-who");
  if (account.signed_in) {
    who.append(element("span", "account-name", "Signed in"));
    const seen = element("span", "account-seen");
    seen.append("Others see you as ", element("strong", "", label));
    who.append(seen);
  } else {
    // A pseudonymous account exists only on a deployment with no sign-in.
    // Say so: nobody can come back to it from another device.
    who.append(element("span", "account-name", label));
    who.append(element("span", "account-seen", "this browser only · how others see you"));
  }
  who.title = account.user_id || "";
  // Sign-out changes state, so it is a POST form rather than a link that a
  // prefetch or a link scanner could follow on the person's behalf.
  const form = element("form", "account-signout");
  form.method = "post";
  form.action = "/auth/sign-out";
  const button = element("button", "account-action", "Sign out");
  button.type = "submit";
  form.appendChild(button);
  slot.replaceChildren(who, form);
  if (gate) gate.hidden = true;
  document.body.dataset.signedIn = "true";
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
    renderSignedIn(account);
    return;
  }
  if (state?.sign_in_required) {
    renderSignedOut(state);
    return;
  }
  slot.replaceChildren();
  if (gate) gate.hidden = true;
}

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
