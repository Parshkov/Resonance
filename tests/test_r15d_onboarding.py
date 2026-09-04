"""R15D hosted-client onboarding acceptance — self-activating harness test.

Runs the black-box onboarding probe (`ops/hosted_onboarding_probe.py`) against a
locally built server, exercising the exact sequence a hosted MCP client (ChatGPT
custom app / Claude custom connector) walks when handed only the canonical `/mcp`
resource URL.

It **skips cleanly** until the canonical OAuth core (#134 R15A) is present on the
served build — detected by RFC 8414 authorization-server metadata at
`/.well-known/oauth-authorization-server`. On today's `main` (demo OAuth only) it
skips; the moment R15A lands, this test activates automatically with no edits.

This lane (#137 R15D) owns acceptance tooling only — the probe speaks HTTP to a
running origin and imports nothing from the OAuth core or the product.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from src.product.server import build_runtime
from src.remote.server import build_httpd

_PROBE_PATH = Path(__file__).resolve().parent.parent / "ops" / "hosted_onboarding_probe.py"
_spec = importlib.util.spec_from_file_location("hosted_onboarding_probe", _PROBE_PATH)
_probe_mod = importlib.util.module_from_spec(_spec)
# Register before exec so the probe's @dataclass can resolve its own module
# (dataclasses look up sys.modules[cls.__module__] during processing).
sys.modules["hosted_onboarding_probe"] = _probe_mod
_spec.loader.exec_module(_probe_mod)
OnboardingProbe = _probe_mod.OnboardingProbe


def _oauth_core_present(base: str) -> bool:
    try:
        with urlopen(base + "/.well-known/oauth-authorization-server", timeout=5) as r:
            return r.status == 200
    except (HTTPError, OSError):
        return False


class HostedOnboardingAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = build_runtime(":memory:",
                                    allowed_origins=frozenset({"http://127.0.0.1"}))
        cls.httpd = build_httpd("127.0.0.1", 0, runtime=cls.runtime)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        if not _oauth_core_present(self.base):
            self.skipTest("R15A canonical OAuth core (#134) not present on this build; "
                          "the onboarding harness self-activates when it lands")

    def test_canonical_onboarding_sequence(self):
        """Full hosted-client sequence: discovery → PKCE authorize → token →
        MCP initialize → tools/list → whoami, plus refresh rotation and revoke."""
        probe = OnboardingProbe(self.base, verbose=False)
        report = probe.run(smoke=True, refresh=True, revoke=True)
        failed = [s["step"] for s in report["steps"] if s["required"] and not s["ok"]]
        self.assertTrue(report["required_all_passed"],
                        f"required onboarding steps failed: {failed}")
        by_name = {s["step"]: s for s in report["steps"]}
        # security-critical negative checks, when the build implements them
        for name in ("old refresh token reuse rejected", "refresh after revoke rejected"):
            if name in by_name:
                self.assertTrue(by_name[name]["ok"], f"{name} did not reject reuse")

    def test_no_bearer_is_challenged_not_served(self):
        """A hosted client presenting no token must get a 401 challenge that
        points at resource metadata — never a served result or a URL-token path."""
        probe = OnboardingProbe(self.base, verbose=False)
        step = probe.unauth_challenge()
        self.assertEqual(step.http_status, 401)
        self.assertTrue(step.data.get("resource_metadata"),
                        "401 must carry WWW-Authenticate resource_metadata pointer")


if __name__ == "__main__":
    unittest.main()
