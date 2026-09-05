"""Real sign-in (2026-09-04).

Resonance exists to introduce people whose reasoning has the same shape. An
anonymous account defeats that at the root: the same person arriving from
Claude, from ChatGPT and from a browser is three unrelated strangers, none of
them is recognised on return, and no one can be told when a match finally
appears. These tests hold the line that an account comes into being only behind
a provider that verified who signed in — and that a deployment with no provider
at all (a local run, this suite) is unaffected.
"""

import json
import sys
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.identity import IdentityService, R11IdentityBackend  # noqa: E402
from src.identity.federation import (  # noqa: E402
    FederatedIdentity,
    configured_providers,
)
from src.identity.models import AuthorizationError, IdentityValidationError  # noqa: E402
from src.persistence import LiveCorpusService  # noqa: E402
from src.product import auth_mount  # noqa: E402
from src.product.auth_mount import AuthMount, SignInStates, safe_next  # noqa: E402
from src.product.server import (  # noqa: E402
    build_runtime,
    serve,
    startup_purge_unsigned,
)
from src.remote.oauth import GrantStore, OAuthCore  # noqa: E402

GOOGLE_ENV = {
    "RESONANCE_AUTH_GOOGLE_CLIENT_ID": "client-id",
    "RESONANCE_AUTH_GOOGLE_CLIENT_SECRET": "client-secret",
}


def _identity() -> IdentityService:
    runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}),
                            seed=False)
    return runtime.identity


class FederatedAccountTests(unittest.TestCase):
    """One provider subject is one account, whatever surface it arrives from."""

    def setUp(self):
        self.identity = _identity()

    def _sign_in(self, subject="sub-1", email="a@example.com", label="Ada"):
        return self.identity.sign_in_federated(
            provider="google", subject=subject, email=email,
            email_verified=True, display_label=label)

    def test_the_same_provider_subject_returns_to_the_same_account(self):
        first = self._sign_in()
        second = self._sign_in()
        self.assertEqual(first.user_id, second.user_id)
        # A fresh session each time: the account is stable, the token is not.
        self.assertNotEqual(first.access_token, second.access_token)

    def test_a_different_subject_is_a_different_account(self):
        self.assertNotEqual(self._sign_in("sub-1").user_id,
                            self._sign_in("sub-2", "b@example.com").user_id)

    def test_an_unverified_address_is_refused_rather_than_stored(self):
        with self.assertRaises(IdentityValidationError):
            self.identity.sign_in_federated(
                provider="google", subject="sub-x", email="x@example.com",
                email_verified=False, display_label="X")
        self.assertIsNone(self.identity.find_user_by_identity("google", "sub-x"))

    def test_claims_carry_the_verified_address_for_the_account(self):
        creds = self._sign_in(email="ada@example.com")
        claims = self.identity.identity_claims(creds.user_id)
        self.assertEqual(claims["email"], "ada@example.com")
        self.assertTrue(claims["email_verified"])
        self.assertEqual(claims["provider"], "google")

    def test_an_account_without_a_sign_in_has_no_claims(self):
        creds = self.identity.register("solo")
        self.assertEqual(self.identity.identity_claims(creds.user_id), {})

    def test_a_provider_subject_cannot_be_moved_onto_another_account(self):
        owner = self._sign_in()
        other = self.identity.register("someone else")
        with self.assertRaises(AuthorizationError):
            self.identity.link_identity_to_account(
                other.user_id, provider="google", subject="sub-1",
                email="a@example.com", email_verified=True)
        self.assertEqual(self.identity.find_user_by_identity("google", "sub-1"),
                         owner.user_id)

    def test_a_revoked_account_does_not_answer_for_its_provider_subject(self):
        creds = self._sign_in()
        self.identity.revoke_account(creds.access_token, confirmed=True)
        self.assertIsNone(self.identity.find_user_by_identity("google", "sub-1"))


class ProviderConfigurationTests(unittest.TestCase):
    def test_a_provider_without_credentials_is_simply_absent(self):
        self.assertEqual(configured_providers({}), {})
        self.assertEqual(configured_providers(
            {"RESONANCE_AUTH_GOOGLE_CLIENT_ID": "only-an-id"}), {})

    def test_a_configured_provider_is_offered(self):
        found = configured_providers(GOOGLE_ENV)
        self.assertEqual(set(found), {"google"})
        target = found["google"].authorize_redirect(
            redirect_uri="https://example.test/auth/callback/google", state="st")
        self.assertTrue(target.startswith("https://accounts.google.com/"))
        self.assertIn("state=st", target)
        self.assertIn("client_id=client-id", target)
        # The secret authenticates the code exchange and never leaves the server.
        self.assertNotIn("client-secret", target)

    def test_display_label_prefers_the_handle_then_the_address(self):
        self.assertEqual(FederatedIdentity("google", "s", "ada@x.test", True, "Ada L")
                         .display_label(), "Ada L")
        self.assertEqual(FederatedIdentity("google", "s", "ada@x.test", True, "")
                         .display_label(), "ada")


class SignInRedirectTests(unittest.TestCase):
    """The redirect back into the site is the classic open-redirect hazard."""

    def test_only_paths_on_this_origin_are_returned_to(self):
        self.assertEqual(safe_next("/collab?x=1"), "/collab?x=1")
        for hostile in ("//evil.test/", "https://evil.test/", "/\\evil.test",
                        "/ok\r\nSet-Cookie: a=b", None, ""):
            self.assertEqual(safe_next(hostile), "/")


class SignInStateTests(unittest.TestCase):
    def test_a_state_is_single_use(self):
        states = SignInStates()
        state, _ = states.issue(provider="google", next_path="/")
        self.assertIsNotNone(states.take(state))
        self.assertIsNone(states.take(state))

    def test_a_state_expires(self):
        now = [1000.0]
        states = SignInStates(clock=lambda: now[0], ttl=60)
        state, _ = states.issue(provider="google", next_path="/")
        now[0] += 61
        self.assertIsNone(states.take(state))


class AuthMountTests(unittest.TestCase):
    def setUp(self):
        self.identity = _identity()
        self.mount = AuthMount(self.identity, cookie_for=lambda t: f"resonance_token={t}",
                               secure_cookies=False, environ=GOOGLE_ENV)

    def _get(self, path, query=None, headers=None):
        return self.mount.handle("GET", path, query or {}, headers or {},
                                 issuer="https://resonance.test")

    def test_the_sign_in_page_offers_the_configured_provider(self):
        response = self._get("/auth/sign-in", {"next": ["/collab"]})
        body = response.body.decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("Continue with Google", body)
        self.assertIn("/auth/start/google?next=%2Fcollab", body)

    def test_start_redirects_to_the_provider_and_binds_the_browser(self):
        response = self._get("/auth/start/google", {"next": ["/collab"]})
        self.assertEqual(response.status, 302)
        self.assertTrue(response.headers["Location"].startswith(
            "https://accounts.google.com/"))
        self.assertIn("redirect_uri=https%3A%2F%2Fresonance.test%2Fauth%2Fcallback%2Fgoogle",
                      response.headers["Location"])
        cookie = "".join(response.cookies)
        self.assertIn(f"{auth_mount.STATE_COOKIE}=", cookie)
        # Lax, not Strict: the provider returns the person with a cross-site
        # top-level GET, which a Strict cookie would not accompany.
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("HttpOnly", cookie)

    def test_an_unknown_provider_does_not_start_a_sign_in(self):
        response = self._get("/auth/start/nowhere", {"next": ["/collab"]})
        self.assertEqual(response.status, 200)
        self.assertIn("not available here", response.body.decode("utf-8"))

    def test_a_callback_without_a_known_state_is_refused(self):
        response = self._get("/auth/callback/google",
                             {"code": ["c"], "state": ["never-issued"]})
        self.assertIn("expired", response.body.decode("utf-8"))

    def test_a_callback_in_another_browser_is_refused(self):
        start = self._get("/auth/start/google", {"next": ["/collab"]})
        state = _query_value(start.headers["Location"], "state")
        # Same state, no state cookie: a browser that did not begin this sign-in.
        response = self._get("/auth/callback/google", {"code": ["c"], "state": [state]})
        self.assertIn("could not be verified in this browser",
                      response.body.decode("utf-8"))

    def test_a_completed_callback_signs_the_person_in_and_returns_them(self):
        start = self._get("/auth/start/google", {"next": ["/collab"]})
        state = _query_value(start.headers["Location"], "state")
        nonce = SimpleCookie("; ".join(start.cookies))[auth_mount.STATE_COOKIE].value
        person = FederatedIdentity("google", "sub-9", "ada@example.test", True, "Ada")
        original = auth_mount.exchange_code
        auth_mount.exchange_code = lambda config, code, redirect_uri: person
        try:
            response = self._get(
                "/auth/callback/google", {"code": ["the-code"], "state": [state]},
                {"Cookie": f"{auth_mount.STATE_COOKIE}={nonce}"})
        finally:
            auth_mount.exchange_code = original
        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers["Location"], "/collab")
        jar = "".join(response.cookies)
        self.assertIn("resonance_token=", jar)
        self.assertIn(f"{auth_mount.STATE_COOKIE}=;", jar)  # the state is spent
        self.assertIsNotNone(self.identity.find_user_by_identity("google", "sub-9"))

    def test_a_provider_that_confirms_no_verified_address_creates_nothing(self):
        start = self._get("/auth/start/google", {"next": ["/"]})
        state = _query_value(start.headers["Location"], "state")
        nonce = SimpleCookie("; ".join(start.cookies))[auth_mount.STATE_COOKIE].value
        original = auth_mount.exchange_code

        def _refuse(config, code, redirect_uri):
            raise auth_mount.FederationError("no verified email")

        auth_mount.exchange_code = _refuse
        try:
            response = self._get(
                "/auth/callback/google", {"code": ["c"], "state": [state]},
                {"Cookie": f"{auth_mount.STATE_COOKIE}={nonce}"})
        finally:
            auth_mount.exchange_code = original
        self.assertEqual(response.status, 200)
        self.assertIn("verified email address", response.body.decode("utf-8"))


class ConsentPageTests(unittest.TestCase):
    """Where a sign-in exists, connecting a client offers no anonymous option."""

    def setUp(self):
        self.identity = _identity()

    def _core(self, *, sign_in: bool) -> OAuthCore:
        return OAuthCore(self.identity, GrantStore(),
                         sign_in_required=lambda: sign_in)

    def _page(self, core, headers=None) -> str:
        result = core.handle("GET", "/oauth/authorize", {
            "response_type": ["code"], "client_id": ["c1"],
            "redirect_uri": ["https://client.test/cb"],
            "code_challenge": ["x" * 43], "code_challenge_method": ["S256"],
            "state": ["st"], "resource": ["https://resonance.test/mcp"],
        }, headers or {}, b"", issuer="https://resonance.test")
        return result.body.decode("utf-8")

    def test_without_a_sign_in_the_page_still_offers_a_guest(self):
        self.assertIn('value="guest"', self._page(self._core(sign_in=False)))

    def test_with_a_sign_in_no_guest_is_offered_and_the_page_leads_to_it(self):
        page = self._page(self._core(sign_in=True))
        self.assertNotIn('value="guest"', page)
        self.assertNotIn('name="recovery_secret"', page)
        self.assertIn("/auth/sign-in?next=", page)
        # Nothing to approve until there is an account to approve it for.
        self.assertNotIn('value="approve"', page)

    def test_with_a_sign_in_a_signed_in_browser_can_approve(self):
        creds = self.identity.sign_in_federated(
            provider="google", subject="sub-1", email="a@example.test",
            email_verified=True, display_label="Ada")
        page = self._page(self._core(sign_in=True),
                          {"Cookie": f"resonance_token={creds.access_token}"})
        self.assertIn(creds.user_id, page)
        self.assertIn('value="approve"', page)
        self.assertIn('name="identity" value="current"', page)

    def test_the_way_back_to_this_consent_screen_survives_the_sign_in(self):
        """The consent URL carries its own query. Escaped as HTML but not as a
        URL, its `&` would split `next` into separate parameters of the sign-in
        page and strand the person on the home page instead of returning them
        to the client that sent them."""
        import html as _html
        import re
        from urllib.parse import unquote

        page = self._page(self._core(sign_in=True))
        href = re.search(r'href="(/auth/sign-in\?next=[^"]*)"', page).group(1)
        target = _html.unescape(href)
        self.assertNotIn("&", target[len("/auth/sign-in?next="):])
        back = unquote(target.split("next=", 1)[1])
        self.assertEqual(safe_next(back), back)
        self.assertTrue(back.startswith("/oauth/authorize?"))
        for expected in ("client_id=c1", "state=st", "code_challenge_method=S256"):
            self.assertIn(expected, back)

    def test_a_replayed_form_cannot_fall_back_to_a_guest(self):
        core = self._core(sign_in=True)
        result = core.handle("POST", "/oauth/authorize", {}, {}, (
            b"response_type=code&client_id=c1&redirect_uri=https%3A%2F%2Fclient.test%2Fcb"
            b"&code_challenge=" + b"x" * 43 + b"&code_challenge_method=S256&state=st"
            b"&resource=https%3A%2F%2Fresonance.test%2Fmcp&decision=approve"
        ), issuer="https://resonance.test")
        self.assertEqual(result.status, 302)
        self.assertIn("error=access_denied", result.headers["Location"])


class UserInfoTests(unittest.TestCase):
    def setUp(self):
        self.identity = _identity()
        self.core = OAuthCore(self.identity, GrantStore())

    def _get(self, headers):
        return self.core.handle("GET", "/oauth/userinfo", {}, headers, b"",
                                issuer="https://resonance.test")

    def test_an_unauthenticated_call_is_challenged(self):
        result = self._get({})
        self.assertEqual(result.status, 401)
        self.assertIn("WWW-Authenticate", result.headers)

    def test_a_signed_in_account_reports_its_verified_address(self):
        creds = self.identity.sign_in_federated(
            provider="google", subject="sub-1", email="ada@example.test",
            email_verified=True, display_label="Ada")
        result = self._get({"Authorization": f"Bearer {creds.access_token}"})
        doc = json.loads(result.body.decode("utf-8"))
        self.assertEqual(doc["sub"], creds.user_id)
        self.assertEqual(doc["email"], "ada@example.test")
        self.assertTrue(doc["email_verified"])
        self.assertEqual(doc["name"], "Ada")

    def test_an_account_with_no_sign_in_reports_no_address(self):
        creds = self.identity.register("solo")
        doc = json.loads(self._get(
            {"Authorization": f"Bearer {creds.access_token}"}).body.decode("utf-8"))
        self.assertEqual(doc["sub"], creds.user_id)
        self.assertNotIn("email", doc)

    def test_the_endpoint_is_advertised(self):
        result = self.core.handle("GET", "/.well-known/oauth-authorization-server",
                                  {}, {}, b"", issuer="https://resonance.test")
        doc = json.loads(result.body.decode("utf-8"))
        self.assertEqual(doc["userinfo_endpoint"],
                         "https://resonance.test/oauth/userinfo")


class HttpSurfaceTests(unittest.TestCase):
    """End-to-end over the real server, with a provider configured."""

    @classmethod
    def setUpClass(cls):
        cls.runtime = build_runtime(":memory:",
                                    allowed_origins=frozenset({"http://127.0.0.1"}),
                                    seed=False)
        cls.httpd = serve("127.0.0.1", 0, runtime=cls.runtime)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def _with_provider(self):
        mount = AuthMount(self.runtime.identity,
                          cookie_for=lambda t: f"resonance_token={t}",
                          secure_cookies=False, environ=GOOGLE_ENV)
        self.runtime.auth_mount = mount
        self.addCleanup(lambda: setattr(self.runtime, "auth_mount", None))

    def test_the_sign_in_page_is_served(self):
        self._with_provider()
        with urlopen(f"{self.base}/auth/sign-in") as response:
            body = response.read().decode("utf-8")
        self.assertIn("Continue with Google", body)
        self.assertIn("never receives your password", body)

    def test_guest_creation_is_refused_where_a_sign_in_exists(self):
        self._with_provider()
        request = Request(f"{self.base}/api/product/guest", data=b"{}",
                          headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)
        body = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(body["error"], "sign_in_required")
        self.assertEqual(body["sign_in_url"], "/auth/sign-in")

    def test_without_a_provider_the_pseudonymous_path_is_untouched(self):
        self.runtime.auth_mount = None
        request = Request(f"{self.base}/api/product/guest", data=b"{}",
                          headers={"Content-Type": "application/json"})
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("user_id", json.loads(response.read().decode("utf-8")))


class RetiringAccountsNobodySignedIntoTests(unittest.TestCase):
    """Applying the product's own rule to what came before it.

    Resonance introduces people, so an account has to belong to someone who can
    be reached. Leaving the thoughts of an account nobody signed into in the
    pool is worse than an empty corpus: a real participant is shown a resonance
    with someone who can never accept an introduction.
    """

    def setUp(self):
        from src.product.server import build_runtime as _build
        from tests.test_standing_search import ORIGIN as SHARE_ORIGIN
        self.runtime = _build(":memory:",
                              allowed_origins=frozenset({SHARE_ORIGIN}),
                              seed=False)
        self.product = self.runtime.product
        self.identity = self.runtime.identity

    def _share(self, creds):
        from tests.test_standing_search import dna, share as _share_thought
        return _share_thought(self.product, creds, dna("ses-aria-plasma-lens",
                                                       f"th-{creds.user_id[-6:]}"))

    def _signed_in(self, subject="sub-1"):
        return self.identity.sign_in_federated(
            provider="google", subject=subject, email=f"{subject}@example.test",
            email_verified=True, display_label="Real person")

    def test_unset_does_nothing_at_all(self):
        self.assertIsNone(startup_purge_unsigned(self.runtime, {}))

    def test_report_counts_without_changing_anything(self):
        ghost = self.product.register("ghost")
        session_id = self._share(ghost)
        result = startup_purge_unsigned(self.runtime,
                                        {"RESONANCE_PURGE_UNSIGNED": "report"})
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["sessions_to_delete"], 1)
        self.assertIsNotNone(self.runtime.live.get_session(session_id))

    def test_it_removes_the_unsigned_and_spares_the_signed_in(self):
        ghost = self.product.register("ghost")
        ghost_session = self._share(ghost)
        real = self._signed_in()
        real_session = self._share(real)

        result = startup_purge_unsigned(self.runtime, {"RESONANCE_PURGE_UNSIGNED": "1"})
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["deleted"], 1)
        self.assertIsNotNone(self.runtime.live.get_session(ghost_session).deleted_at)
        self.assertIsNone(self.runtime.live.get_session(real_session).deleted_at)

    def test_an_explicit_keep_list_is_honoured(self):
        ghost = self.product.register("ghost")
        session_id = self._share(ghost)
        result = startup_purge_unsigned(self.runtime, {
            "RESONANCE_PURGE_UNSIGNED": "1",
            "RESONANCE_PURGE_KEEP": session_id,
        })
        self.assertEqual(result["sessions_to_delete"], 0)
        self.assertIsNone(self.runtime.live.get_session(session_id).deleted_at)

    def test_running_it_twice_finds_nothing_left_to_do(self):
        ghost = self.product.register("ghost")
        self._share(ghost)
        startup_purge_unsigned(self.runtime, {"RESONANCE_PURGE_UNSIGNED": "1"})
        again = startup_purge_unsigned(self.runtime, {"RESONANCE_PURGE_UNSIGNED": "1"})
        self.assertEqual(again["sessions_to_delete"], 0)


def _query_value(url: str, key: str) -> str:
    from urllib.parse import parse_qs, urlsplit
    return parse_qs(urlsplit(url).query)[key][0]


if __name__ == "__main__":
    unittest.main()
