"""Client ID Metadata Documents (2026-09-05).

Dynamic registration makes a directory that connects thousands of people create
thousands of registrations for one client, which is why both Anthropic and
OpenAI prefer CIMD. The price is that the authorization server now fetches a URL
chosen by whoever is asking — a server-side request forgery primitive unless it
is fenced in. Most of what follows is that fence.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.remote import cimd  # noqa: E402
from src.remote.cimd import (  # noqa: E402
    CimdError,
    ClientMetadataCache,
    fetch_client_metadata,
    looks_like_cimd,
)
from src.remote.oauth import GrantStore, OAuthCore  # noqa: E402

CLIENT_URL = "https://claude.ai/api/mcp/client-metadata.json"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def document(**overrides):
    doc = {
        "client_id": CLIENT_URL,
        "client_name": "Claude",
        "redirect_uris": [REDIRECT],
        "scope": "resonance offline_access",
    }
    doc.update(overrides)
    return doc


def reader_for(doc):
    return lambda client_id: dict(doc)


class ShapeTests(unittest.TestCase):
    def test_only_an_https_url_is_a_metadata_document(self):
        self.assertTrue(looks_like_cimd(CLIENT_URL))
        for other in ("resonance-client-abc", "http://claude.ai/x", "", None):
            self.assertFalse(looks_like_cimd(other))

    def test_a_registered_client_id_is_not_fetched(self):
        with self.assertRaises(CimdError):
            fetch_client_metadata("resonance-client-abc")


class DocumentTests(unittest.TestCase):
    def test_a_valid_document_names_the_client_and_its_redirects(self):
        found = fetch_client_metadata(CLIENT_URL, reader=reader_for(document()))
        self.assertEqual(found.client_name, "Claude")
        self.assertTrue(found.allows(REDIRECT))

    def test_a_document_cannot_claim_a_different_client_id(self):
        """Without this the URL stops being the client's identity: anyone could
        serve a document claiming to be someone else's client."""
        with self.assertRaises(CimdError):
            fetch_client_metadata(CLIENT_URL, reader=reader_for(
                document(client_id="https://evil.test/other.json")))

    def test_a_document_with_no_usable_redirect_uris_is_refused(self):
        missing = document()
        missing.pop("redirect_uris")
        candidates = [missing]
        for bad in ({"redirect_uris": []}, {"redirect_uris": "nope"},
                    {"redirect_uris": [""]}, {"redirect_uris": [123]}):
            candidates.append(document(**bad))
        for doc in candidates:
            with self.assertRaises(CimdError, msg=repr(doc.get("redirect_uris"))):
                fetch_client_metadata(CLIENT_URL, reader=reader_for(doc))

    def test_redirect_matching_is_exact_and_not_by_prefix(self):
        """Prefix matching on redirect URIs is the classic way an authorization
        code is delivered to someone other than the client."""
        found = fetch_client_metadata(CLIENT_URL, reader=reader_for(document()))
        self.assertFalse(found.allows(REDIRECT + "/../evil"))
        self.assertFalse(found.allows(REDIRECT + "?x=1"))
        self.assertFalse(found.allows("https://claude.ai/api/mcp/auth_callback2"))


class RequestForgeryTests(unittest.TestCase):
    """The fence. Each of these is a way to point the server somewhere private."""

    def _refused(self, url):
        with self.assertRaises(CimdError, msg=url):
            cimd._validate_url(url)

    def test_plain_http_is_refused(self):
        self._refused("http://claude.ai/x.json")

    def test_credentials_in_the_url_are_refused(self):
        self._refused("https://user:pass@claude.ai/x.json")

    def test_a_fragment_is_refused(self):
        self._refused("https://claude.ai/x.json#frag")

    def test_loopback_and_private_and_link_local_are_refused(self):
        for host in ("127.0.0.1", "localhost", "10.0.0.1", "192.168.1.1",
                     "172.16.0.1", "169.254.169.254", "[::1]", "0.0.0.0"):
            self._refused(f"https://{host}/x.json")

    def test_the_cloud_metadata_endpoint_is_refused(self):
        # The single most valuable target of an SSRF on a hosted service.
        self._refused("https://169.254.169.254/latest/meta-data/")

    def test_a_public_host_passes(self):
        self.assertEqual(cimd._validate_url(CLIENT_URL), CLIENT_URL)

    def test_a_host_resolving_to_any_private_address_is_refused(self):
        """A name that returns one public and one private address would
        otherwise be a way in, so every resolved address is checked."""
        real = cimd.socket.getaddrinfo
        cimd.socket.getaddrinfo = lambda *a, **k: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ]
        try:
            self._refused("https://mixed.test/x.json")
        finally:
            cimd.socket.getaddrinfo = real


class CacheTests(unittest.TestCase):
    def test_a_document_is_fetched_once_within_its_ttl(self):
        calls = []

        def counting_reader(client_id):
            calls.append(client_id)
            return document()

        now = [1000.0]
        cache = ClientMetadataCache(ttl=300, clock=lambda: now[0])
        for _ in range(5):
            cache.get(CLIENT_URL, reader=counting_reader)
        self.assertEqual(len(calls), 1)
        now[0] += 301
        cache.get(CLIENT_URL, reader=counting_reader)
        self.assertEqual(len(calls), 2)


class AuthorizationTests(unittest.TestCase):
    """CIMD end to end through the authorization endpoint."""

    def setUp(self):
        from src.product.server import build_runtime
        runtime = build_runtime(":ephemeral:",
                                allowed_origins=frozenset({"http://127.0.0.1"}),
                                seed=False)
        self.identity = runtime.identity
        self.core = OAuthCore(self.identity, GrantStore())
        self.core.client_metadata = ClientMetadataCache()
        self.core.client_metadata.get = lambda client_id, reader=None: (
            fetch_client_metadata(client_id, reader=reader_for(document())))

    def _authorize(self, *, client_id=CLIENT_URL, redirect_uri=REDIRECT):
        return self.core.handle("GET", "/oauth/authorize", {
            "response_type": ["code"], "client_id": [client_id],
            "redirect_uri": [redirect_uri],
            "code_challenge": ["x" * 43], "code_challenge_method": ["S256"],
            "state": ["st"], "resource": ["https://resonance.test/mcp"],
        }, {}, b"", issuer="https://resonance.test")

    def test_a_cimd_client_reaches_the_consent_page_without_registering(self):
        result = self._authorize()
        self.assertEqual(result.status, 200)
        self.assertIn("Claude", result.body.decode("utf-8"))

    def test_a_redirect_uri_outside_the_document_is_refused_on_page(self):
        """Refused here, not redirected to — redirecting an unvalidated
        redirect_uri is itself the open redirect."""
        result = self._authorize(redirect_uri="https://evil.test/steal")
        self.assertEqual(result.status, 400)
        self.assertNotIn("Location", result.headers)

    def test_the_capability_is_advertised_with_its_companion(self):
        """A host selects CIMD only when it sees both of these, so they are
        pinned together."""
        result = self.core.handle("GET", "/.well-known/oauth-authorization-server",
                                  {}, {}, b"", issuer="https://resonance.test")
        doc = json.loads(result.body.decode("utf-8"))
        self.assertTrue(doc["client_id_metadata_document_supported"])
        self.assertIn("none", doc["token_endpoint_auth_methods_supported"])

    def test_dynamic_registration_still_works_alongside_it(self):
        result = self.core.handle("POST", "/oauth/register", {}, {}, json.dumps({
            "redirect_uris": ["https://client.test/cb"], "client_name": "Legacy",
        }).encode("utf-8"), issuer="https://resonance.test")
        self.assertEqual(result.status, 201)


if __name__ == "__main__":
    unittest.main()
