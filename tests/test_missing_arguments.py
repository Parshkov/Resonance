"""What a tool says when a required argument is missing (2026-09-05).

Found against production: calling resonance_stop_sharing without session_id
answered "resource unavailable to authenticated subject". The empty string
belongs to nobody, so the ownership check rejected it — and the caller was
told, in effect, "that is someone else's data".

An assistant reading that would tell the person their thought could not be
withdrawn because it was not theirs, which is alarming and false. The person
would have no way to know the assistant had simply left out an argument.

These pin the distinction: a missing argument is the caller's mistake and says
so; an argument naming someone else's data still fails as authorization.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import (  # noqa: E402
    BridgeError, RemoteMCPBridge, classify_error)
from src.product.server import build_runtime  # noqa: E402


class MissingArgumentTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.token = self.runtime.product.register_guest().access_token

    def _fails_with(self, tool, arguments):
        with self.assertRaises(BridgeError) as caught:
            getattr(self.bridge, tool)(self.token, arguments)
        return caught.exception

    def test_a_missing_id_names_itself_and_is_not_called_authorization(self):
        for tool, arguments, missing in (
            ("tool_stop_sharing", {"confirm": True}, "session_id"),
            ("tool_explain_match", {"session_id": "ses-x"}, "result_id"),
            ("tool_explain_match", {"result_id": "result-x"}, "session_id"),
            ("tool_share_thought",
             {"confirm": True, "request_id": "r1"}, "draft_id"),
        ):
            with self.subTest(f"{tool} without {missing}"):
                error = self._fails_with(tool, arguments)
                self.assertEqual(error.code, "validation_failed")
                self.assertIn(missing, str(error))

    def test_an_id_that_belongs_to_someone_else_still_fails_as_authorization(self):
        """The clearer message must not have widened into hiding real refusals."""
        with self.assertRaises(Exception) as caught:
            self.bridge.tool_stop_sharing(
                self.token,
                {"session_id": "ses-belonging-to-somebody-else", "confirm": True})
        code, _callers_fault = classify_error(caught.exception)
        self.assertEqual(code, "authorization_failed")


if __name__ == "__main__":
    unittest.main()
