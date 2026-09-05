// Who you are on this page.
//
// Resonance introduces people whose reasoning has the same shape, so the
// account is the product's subject, not an implementation detail: a visitor
// should be able to see whether they are signed in, as whom, and how to leave.
// Where a deployment offers a sign-in, that is step 1 of the loop and the
// page says so in the body, not only in the masthead. Where it offers none
// (a local run), the pseudonymous account is named for what it is.

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

// The consent pill is filled in by the module that reads the authorized
// record, which needs a session to read it. Signed out there is no session and
// never will be one, so the pill sat on "Checking consent" indefinitely. Say
// the true thing instead: there is nothing to check yet.
function markConsentUnknown() {
  const pill = document.getElementById("header-consent");
  if (!pill || pill.dataset.shared !== undefined) return;
  for (const span of pill.querySelectorAll("span")) {
    if (/checking consent/i.test(span.textContent || "")) {
      span.textContent = "Not signed in";
    }
  }
}

function signInLink(base, className) {
  const link = element("a", className, "Sign in");
  link.href = signInHref(base);
  return link;
}

function renderSignedOut(state, urgent = false) {
  markConsentUnknown();
  const link = signInLink(state.sign_in_url, "account-action");
  if (urgent) link.classList.add("account-action-urgent");
  slot.replaceChildren(link);
  if (gate && gateActions) {
    gateActions.replaceChildren(signInLink(state.sign_in_url, "button button-primary"));
    gate.hidden = false;
  }
}

function renderSignedIn(account) {
  const label = (account.display_label || account.user_id || "").trim();
  const who = element("span", "account-who");
  who.append(element("span", "", label));
  // A pseudonymous account exists only on a deployment with no sign-in. Say
  // so: nobody can come back to it from another device.
  who.append(element("small", "", account.signed_in
    ? "signed in" : "pseudonymous · this browser only"));
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
    slot.hidden = false;
    renderSignedIn(account);
    return;
  }
  if (state?.sign_in_required) {
    slot.hidden = false;
    renderSignedOut(state);
    return;
  }
  slot.hidden = true;
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
  slot.hidden = false;
  renderSignedOut({sign_in_url: event.detail?.signInUrl, sign_in_required: true}, true);
  gate?.scrollIntoView({block: "nearest"});
});
