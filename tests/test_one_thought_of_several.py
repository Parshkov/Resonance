"""A person with more than one thought here, and what the page says to them.

Three defects, none of which an empty instance can show, because each needs
two thoughts from one person:

1. Which thought the page was "about" was a coin toss. `owned_sessions` comes
   back in the store's order -- by session id, which is random hex -- and the
   page took the last row. So did the chat's `resonance_discover` without a
   `session_id`. Both now mean the thought most recently made discoverable,
   by one rule in one place.

2. Withdraw one of two, and the page kept drawing the withdrawn one under
   "What others can see": it only re-read when sharing flipped between
   something and nothing. Now it re-reads when what is discoverable changes.

3. "Private · nothing of yours is discoverable" was said to a person whose
   thought was withdrawn, not private. The line is now built from the three
   counts the chat's whoami reports, and "nothing of yours is discoverable"
   is only ever said of a person for whom it is true.

These fail against the code before the change and pass after it; the ones
that reach the browser modules run them under node, without a document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.product.mcp_bridge import RemoteMCPBridge, current_shared_session
from src.product.phrasing import say
from src.product.server import UI_DIR
from src.product.web_server import _owned_live_session
from tests.test_shared_list import Person, _live_server, thought

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


# ---- 1. the thought this page is about ------------------------------------

class _Event:
    def __init__(self, user_id, session_id, event_type, created_at, payload=None):
        self.user_id, self.session_id = user_id, session_id
        self.event_type, self.created_at = event_type, created_at
        self.payload = payload or {}


class _Actor:
    user_id = "person-1"


class _FakeProduct:
    """Just enough of the product to hand `current_shared_session` its inputs,
    with the store's order under our control."""

    def __init__(self, rows, events):
        self.rows, self.events = rows, events
        self.identity = self

    def owned_sessions(self, token):
        return list(self.rows)

    def authenticate(self, token):
        return _Actor()

    @property
    def backend(self):
        return self

    def list_identity_events(self):
        return list(self.events)


class WhichThoughtTests(unittest.TestCase):
    def test_the_most_recently_shared_thought_not_the_last_row(self):
        from src.ingestion.identity import INGESTION_SHARED
        # The store lists "older" last (its ids sort that way); the person
        # shared "newer" more recently. The old rule took the last row.
        rows = [{"session_id": "ses-newer", "share_state": "discoverable", "created_at": "t1"},
                {"session_id": "ses-older", "share_state": "discoverable", "created_at": "t0"}]
        events = [_Event("person-1", "ses-older", INGESTION_SHARED, "2026-09-01T10:00:00"),
                  _Event("person-1", "ses-newer", INGESTION_SHARED, "2026-09-02T10:00:00")]
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-newer")
        # Re-sharing the older one later makes it the current one: sharing is
        # the act that changes what others can see.
        from src.identity.service import CONSENT_SET
        events.append(_Event("person-1", "ses-older", CONSENT_SET, "2026-09-03T10:00:00",
                             {"share_thought_dna": True}))
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-older")
        # A consent event that did NOT make it discoverable is not a share.
        events.append(_Event("person-1", "ses-newer", CONSENT_SET, "2026-09-04T10:00:00",
                             {"share_thought_dna": False}))
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-older")

    def test_only_discoverable_thoughts_count_and_none_is_none(self):
        rows = [{"session_id": "ses-a", "share_state": "revoked", "created_at": "t0"},
                {"session_id": "ses-b", "share_state": "prepared_private", "created_at": "t1"}]
        self.assertIsNone(current_shared_session(_FakeProduct(rows, []), "tok"))

    def test_without_a_consent_log_the_answer_is_still_the_same_every_time(self):
        # Seeded records have no consent event: fall back to when the thought
        # was prepared, then to the id, so a person never sees the page
        # change its mind between two reads.
        rows = [{"session_id": "ses-z", "share_state": "discoverable", "created_at": "t0"},
                {"session_id": "ses-a", "share_state": "discoverable", "created_at": "t1"}]
        self.assertEqual(current_shared_session(_FakeProduct(rows, []), "tok"), "ses-a")
        tied = [{"session_id": "ses-z", "share_state": "discoverable", "created_at": "t0"},
                {"session_id": "ses-a", "share_state": "discoverable", "created_at": "t0"}]
        self.assertEqual(current_shared_session(_FakeProduct(tied, []), "tok"), "ses-z")
        self.assertEqual(current_shared_session(_FakeProduct(list(reversed(tied)), []), "tok"), "ses-z")


class OverHttpTests(unittest.TestCase):
    """One person, two thoughts, over the routes the page and the chat use."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.base, cls.runtime = _live_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def context_topic(self, person: Person) -> str:
        _, context = person.request("GET", "/api/context")
        return context["presentation"]["topic"]

    def test_the_page_is_about_the_thought_shared_last_whatever_its_id(self):
        person = Person(self.base)
        person.arrive()
        shared = []
        for i in range(6):
            topic = f"Thought number {i}"
            shared.append((topic, person.share(thought(topic, [f"a{i}", f"b{i}", f"c{i}"]))))
            # The old rule picked the greatest id. Keep sharing until the
            # newest thought is not the one with the greatest id, so that the
            # old rule and the right one disagree, then check the right one.
            if shared[-1][1] != max(session_id for _, session_id in shared):
                break
        newest_topic, newest_id = shared[-1]
        self.assertEqual(self.context_topic(person), newest_topic)
        self.assertEqual(_owned_live_session(self.runtime.product, person.token), newest_id)
        # And the chat means the same thought when it is not told which.
        bridge = RemoteMCPBridge(self.runtime.product)
        self.assertEqual(bridge._default_session(person.token), newest_id)

    def test_stop_sharing_from_the_page_withdraws_that_thought_and_says_so(self):
        person = Person(self.base)
        person.arrive()
        first = person.share(thought("Kept out there", ["deadline", "skipped review", "rework"]))
        second = person.share(thought("Taken back", ["fertiliser", "salt", "root damage"]))
        self.assertEqual(self.context_topic(person), "Taken back")

        # The page's own "Stop sharing" control makes exactly this call.
        _, answer = person.request("POST", "/api/webmcp/consent",
                                   {"request_id": "stop-1", "shared": False, "confirm": True})
        self.assertEqual(answer["session_id"], second)
        self.assertTrue(answer["revoked"])
        self.assertFalse(answer["discoverable"], "the fact about the thought")
        self.assertFalse(answer["shared"], "also about the thought, as the chat tool's is")
        self.assertEqual(answer["still_discoverable"], 1, "the fact about the person")
        # What they are told is true of the thought, then true of them.
        self.assertIn("That thought is not discoverable any more", answer["say"])
        self.assertIn("1 other thought of yours is still discoverable", answer["say"])
        self.assertNotIn("Nothing of yours", answer["say"])

        # The page now draws the one that is still out there.
        self.assertEqual(self.context_topic(person), "Kept out there")
        self.assertEqual(_owned_live_session(self.runtime.product, person.token), first)

        # And the chat says the same three things about this person.
        theirs = RemoteMCPBridge(self.runtime.product).tool_whoami(person.token, {})
        self.assertEqual(theirs["shared_thoughts"], [first])
        self.assertEqual(theirs["withdrawn_thoughts"], [second])
        self.assertEqual(theirs["private_thoughts"], [])
        _, mine = person.request("GET", "/api/product/mine")
        self.assertEqual(mine["counts"], {"discoverable": 1, "private": 0, "withdrawn": 1})

        # Taking back the last one: now, and only now, nothing of theirs is.
        _, answer = person.request("POST", "/api/webmcp/consent",
                                   {"request_id": "stop-2", "shared": False, "confirm": True})
        self.assertEqual(answer["session_id"], first)
        self.assertEqual(answer["still_discoverable"], 0)
        self.assertIn("Nothing of yours is discoverable now", answer["say"])

    def test_the_chat_tool_says_the_same_about_the_person(self):
        person = Person(self.base)
        person.arrive()
        first = person.share(thought("One", ["a", "b", "c"]))
        person.share(thought("Two", ["d", "e", "f"]))
        bridge = RemoteMCPBridge(self.runtime.product)
        result = bridge.tool_stop_sharing(person.token, {"session_id": first, "confirm": True})
        self.assertEqual(result["still_discoverable"], 1)
        self.assertIn("1 other thought of yours is still discoverable",
                      say("resonance_stop_sharing", result))
        # A result without the count (an older client's wire) says only what
        # it knows: the thought, and nothing about the person.
        older = {k: v for k, v in result.items() if k != "still_discoverable"}
        self.assertEqual(say("resonance_stop_sharing", older),
                         "Withdrawn. That thought is not discoverable any more, and it will "
                         "not be reported to anyone as a match.")


# ---- 2 and 3. what the page does and says --------------------------------

def _node(script: str, *argv: str) -> dict:
    done = subprocess.run([NODE, "--input-type=module", "-e", script, "--", *argv],
                          capture_output=True, text=True, timeout=30, cwd=str(REPO))
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


WATCHER_SCRIPT = """
import { consentWatcher } from %(module)s;
const announcements = JSON.parse(process.argv[1]);
const rereads = [];
const watch = consentWatcher(() => rereads.push(true));
const trace = announcements.map((detail) => { watch(detail); return rereads.length; });
console.log(JSON.stringify(trace));
"""


@unittest.skipUnless(NODE, "node is not installed; the page module cannot be run here")
class RereadOnConsentTests(unittest.TestCase):
    def trace(self, *announcements) -> list[int]:
        script = WATCHER_SCRIPT % {"module": json.dumps(str(UI_DIR / "app.mjs"))}
        return _node(script, json.dumps(list(announcements)))

    def test_withdrawing_one_of_two_makes_the_page_re_read(self):
        # Boot: two discoverable. Withdraw one: still "shared", but not the
        # same thoughts -- the page must re-read or keep drawing the withdrawn
        # one under "What others can see".
        self.assertEqual(self.trace(
            {"shared": True, "discoverable": ["ses-a", "ses-b"]},
            {"shared": True, "discoverable": ["ses-a"]},
        ), [0, 1])

    def test_nothing_changed_costs_nothing(self):
        # Discovery is rate-limited; an announcement that changes nothing
        # must not spend a read. Order of the list is not a change either.
        self.assertEqual(self.trace(
            {"shared": True, "discoverable": ["ses-a", "ses-b"]},
            {"shared": True, "discoverable": ["ses-b", "ses-a"]},
            {"shared": True},                       # webmcp_live: only knows yes/no
            {"shared": True, "discoverable": ["ses-a", "ses-b"]},
        ), [0, 0, 0, 0])

    def test_a_flip_still_re_reads_with_or_without_the_list(self):
        self.assertEqual(self.trace(
            {"shared": False},
            {"shared": True},
            {"shared": True, "discoverable": ["ses-a"]},
            {"shared": False, "discoverable": []},
            {"shared": True, "discoverable": ["ses-b"]},
        ), [0, 1, 1, 2, 3])

    def test_a_second_share_from_a_chat_moves_the_page_to_it(self):
        self.assertEqual(self.trace(
            {"shared": True, "discoverable": ["ses-a"]},
            {"shared": True, "discoverable": ["ses-a", "ses-b"]},
        ), [0, 1])


WORDS_SCRIPT = """
import { shareStateWords, stopSharingMeans } from %(module)s;
const cases = JSON.parse(process.argv[1]);
console.log(JSON.stringify(cases.map((counts) => [shareStateWords(counts), stopSharingMeans(counts)])));
"""

SESSION_IMPORT = 'import { apiFetch } from "/session.mjs";'


@unittest.skipUnless(NODE, "node is not installed; the page module cannot be run here")
class ShareLineTests(unittest.TestCase):
    """The words beside the status light, run from the module itself.

    collab_ui.mjs imports the page's session module by URL, which node cannot
    resolve, so the copy under test has that one line replaced by stubs; the
    sentences are pure functions of the counts and touch neither.
    """

    @classmethod
    def setUpClass(cls):
        source = (UI_DIR / "collab_ui.mjs").read_text(encoding="utf-8")
        assert SESSION_IMPORT in source, "the import this stubs has moved"
        cls.tmp = tempfile.TemporaryDirectory()
        cls.module = Path(cls.tmp.name) / "collab_ui.mjs"
        cls.module.write_text(source.replace(
            SESSION_IMPORT, "const apiFetch = () => {};"),
            encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def words(self, *cases) -> list[list[str]]:
        script = WORDS_SCRIPT % {"module": json.dumps(str(self.module))}
        return _node(script, json.dumps(list(cases)))

    def test_nothing_of_yours_is_only_said_when_nothing_of_yours_is(self):
        line, _ = self.words({"discoverable": 1, "private": 0, "withdrawn": 1})[0]
        self.assertEqual(line, "Discoverable · 1 thought · still looking · 1 thought withdrawn")
        self.assertNotIn("Nothing of yours", line)
        self.assertNotIn("Private", line)

    def test_withdrawn_is_not_private(self):
        line, _ = self.words({"discoverable": 0, "private": 0, "withdrawn": 1})[0]
        self.assertEqual(line, "Nothing of yours is discoverable · 1 thought withdrawn")
        self.assertNotIn("Private", line)
        line, _ = self.words({"discoverable": 0, "private": 1, "withdrawn": 0})[0]
        self.assertEqual(line, "Nothing of yours is discoverable · 1 thought kept private here")

    def test_three_facts_three_clauses(self):
        line, _ = self.words({"discoverable": 2, "private": 1, "withdrawn": 3})[0]
        self.assertEqual(line, "Discoverable · 2 thoughts · still looking · "
                               "3 thoughts withdrawn · 1 thought kept private here")
        line, _ = self.words({"discoverable": 0, "private": 0, "withdrawn": 0})[0]
        self.assertEqual(line, "Nothing of yours is discoverable")
        line, _ = self.words({})[0]
        self.assertEqual(line, "Nothing of yours is discoverable")

    def test_stop_sharing_says_what_will_happen_to_the_others(self):
        alone, one_other, two_others = [means for _, means in self.words(
            {"discoverable": 1}, {"discoverable": 2}, {"discoverable": 3})]
        self.assertEqual(alone, "This thought leaves discovery now and stops looking. "
                                "Anyone it matched stops seeing it.")
        self.assertEqual(one_other, alone + " Your other thought stays discoverable.")
        self.assertEqual(two_others, alone + " Your 2 other thoughts stay discoverable.")


class OnThePageTests(unittest.TestCase):
    module = (UI_DIR / "collab_ui.mjs").read_text(encoding="utf-8")
    app = (UI_DIR / "app.mjs").read_text(encoding="utf-8")

    def test_the_line_reads_the_same_three_states_the_chat_reports(self):
        self.assertIn('"/api/product/mine"', self.module)
        # The old line, as code (a comment may still quote it to say why it
        # went): one sentence for every person who had nothing discoverable,
        # whatever state their thoughts were in.
        self.assertNotIn('"Private · nothing of yours is discoverable")', self.module)
        self.assertIn("shareStateWords(counts)", self.module)

    def test_stopping_asks_once_inline_never_in_a_browser_dialog(self):
        self.assertNotIn("confirm(", self.module)
        self.assertIn("Yes, stop", self.module)
        self.assertIn("Keep sharing", self.module)

    def test_the_page_re_reads_on_any_consent_change_not_only_a_flip(self):
        self.assertIn("consentWatcher", self.app)
        self.assertNotIn("lastShared", self.app)
        # The identifiers the announcement carries are compared, never shown.
        for line in self.module.splitlines():
            if "session_id" in line and "discoverable" in line:
                self.assertNotIn("textContent", line)
                self.assertNotIn("dataset", line)


if __name__ == "__main__":
    unittest.main()
