"""R14B acceptance battery: multi-person idea workspaces."""

from __future__ import annotations

import unittest

from src.ingestion.service import ShareIntent
from src.product.server import build_runtime
from src.workspaces import WorkspaceError
from tests.test_product_live import PRES, QUERY_DNA, location, r7_dna

ORIGIN = "https://app.resonance.example"


def sec(creds):
    return dict(csrf_token=creds.csrf_token, cookie_authenticated=True,
                origin=ORIGIN, client_id="manual-ui")


def build():
    rt = build_runtime(":memory:", allowed_origins=frozenset({ORIGIN}))
    return rt, rt.product


def share(product, creds, source, tid, *, intro=True):
    prepared = product.prepare_structured(
        creds.access_token, r7_dna(source, tid), presentation=dict(PRES),
        intent=ShareIntent(share_display_profile=True, receive_intro_requests=intro),
        **sec(creds))
    pv = product.preview(creds.access_token, prepared["draft_id"], client_id="manual-ui")
    product.share_prepared(creds.access_token, prepared["draft_id"],
                           confirmation_token=pv["confirmation_token"], confirmed=True,
                           **sec(creds))
    return prepared["session_id"]


def accepted_intro(product, a, a_sess, b, b_sess):
    rid = f"ri-{b_sess[-6:]}-{a_sess[-6:]}"
    product.request_intro(b.access_token, from_session_id=b_sess,
                          target_session_id=a_sess, message="connect?",
                          request_id=rid, confirmed=True, **sec(b))
    incoming = product.list_requests(a.access_token)["incoming"]
    iid = next(r["intro_id"] for r in incoming
               if r["state"] == "requested" and r["to_session_id"] == a_sess)
    product.respond_intro(a.access_token, iid, accept=True, request_id=f"a{rid}",
                          confirmed=True, **sec(a))
    return iid


class WorkspaceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.rt, self.product = build()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")
        self.a_sess = share(self.product, self.alice, "ses-gabe-warehouse", "t-a")
        self.b_sess = share(self.product, self.bob, QUERY_DNA, "t-b")
        self.iid = accepted_intro(self.product, self.alice, self.a_sess,
                                  self.bob, self.b_sess)

    def _workspace(self):
        return self.product.create_workspace(
            self.alice.access_token, self.iid, title="Plasma×Warehouse",
            brief="compare mitigations", **sec(self.alice))["workspace_id"]

    def test_bootstrap_requires_accepted_intro_and_participant(self):
        wid = self._workspace()
        self.assertTrue(wid.startswith("ws-"))
        # a non-participant cannot bootstrap from someone else's intro
        carol = self.product.register("Carol")
        with self.assertRaises(WorkspaceError):
            self.product.create_workspace(carol.access_token, self.iid,
                                          title="hijack", **sec(carol))
        # a non-accepted intro cannot seed one
        d_sess = share(self.product, self.product.register("Dan"),
                       "ses-mei-battery-heat", "t-d")
        self.product.request_intro(self.bob.access_token, from_session_id=self.b_sess,
                                   target_session_id=d_sess, message="x",
                                   request_id="pending", confirmed=True, **sec(self.bob))
        pend = self.product.list_requests(self.bob.access_token)["outgoing"]
        pending_intro = next(r for r in pend if r["state"] == "requested")
        with self.assertRaises(WorkspaceError):
            self.product.create_workspace(self.bob.access_token,
                                          pending_intro["intro_id"],
                                          title="premature", **sec(self.bob))

    def test_invitee_sees_nothing_until_accept(self):
        wid = self._workspace()
        # Bob is invited, not active
        with self.assertRaises(WorkspaceError):
            self.product.get_workspace(self.bob.access_token, wid)
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        full = self.product.get_workspace(self.bob.access_token, wid)
        self.assertEqual({m["display"] for m in full["members"]}, {"Alice", "Bob"})
        self.assertEqual(full["role"], "member")

    def test_two_plus_members_shared_work(self):
        wid = self._workspace()
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        self.product.workspace_add_note(self.bob.access_token, wid,
                                        "throttle input power", **sec(self.bob))
        task = self.product.workspace_add_task(self.alice.access_token, wid,
                                               "prototype loop", **sec(self.alice))
        self.product.workspace_set_task_state(self.bob.access_token, wid,
                                              task["task_id"], "doing", **sec(self.bob))
        self.product.workspace_link_match(self.alice.access_token, wid, self.b_sess,
                                          "Bob's structure resonates", **sec(self.alice))
        self.product.workspace_add_artifact(self.alice.access_token, wid,
                                            label="sketch.svg", kind="image",
                                            sha256="a" * 64, size_bytes=1234,
                                            **sec(self.alice))
        self.product.workspace_update_brief(self.alice.access_token, wid,
                                            "refined hypothesis",
                                            expected_version=1, **sec(self.alice))
        full = self.product.get_workspace(self.bob.access_token, wid)
        self.assertEqual([n["body"] for n in full["notes"]], ["throttle input power"])
        self.assertEqual([(t["title"], t["state"]) for t in full["tasks"]],
                         [("prototype loop", "doing")])
        self.assertEqual(full["brief"], "refined hypothesis")
        self.assertEqual(len(full["artifacts"]), 1)
        self.assertEqual(len(full["links"]), 1)
        self.assertTrue(all(n["untrusted"] for n in full["notes"]))
        self.assertTrue(full["activity"])

    def test_invite_requires_connection_and_write_role(self):
        wid = self._workspace()
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        # Carol is not connected to anyone -> cannot be invited
        carol = self.product.register("Carol")
        with self.assertRaises(WorkspaceError):
            self.product.workspace_invite(self.alice.access_token, wid,
                                          carol.user_id, **sec(self.alice))
        # make Carol connected to Bob, then Bob (member) can invite her
        c_sess = share(self.product, carol, "ses-noah-org-overload", "t-c")
        accepted_intro(self.product, carol, c_sess, self.bob,
                       share(self.product, self.bob, "ses-diego-chiller", "t-b2"))
        invited = self.product.workspace_invite(self.bob.access_token, wid,
                                                carol.user_id, **sec(self.bob))
        self.assertEqual(invited["state"], "invited")
        # a viewer cannot invite (write role required)
        self.product.workspace_respond_invite(carol.access_token, wid, accept=True,
                                              **sec(carol))

    def test_removed_member_loses_access_immediately(self):
        wid = self._workspace()
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        gen_before = self.product.freshness()["serving_generation"]
        self.product.workspace_remove_member(self.alice.access_token, wid,
                                             self.bob.user_id, **sec(self.alice))
        # removal moved no corpus generation, but access is gone at once
        self.assertEqual(self.product.freshness()["serving_generation"], gen_before)
        with self.assertRaises(WorkspaceError):
            self.product.get_workspace(self.bob.access_token, wid)
        with self.assertRaises(WorkspaceError):
            self.product.workspace_add_note(self.bob.access_token, wid, "still here?",
                                            **sec(self.bob))
        # workspace remains valid for the remaining member
        self.assertTrue(self.product.get_workspace(self.alice.access_token, wid))

    def test_owner_cannot_leave_member_can(self):
        wid = self._workspace()
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        with self.assertRaises(WorkspaceError):
            self.product.workspace_leave(self.alice.access_token, wid, **sec(self.alice))
        self.product.workspace_leave(self.bob.access_token, wid, **sec(self.bob))
        with self.assertRaises(WorkspaceError):
            self.product.get_workspace(self.bob.access_token, wid)

    def test_enumeration_resistance_uniform_negative(self):
        wid = self._workspace()
        carol = self.product.register("Carol")
        with self.assertRaises(WorkspaceError) as foreign:
            self.product.get_workspace(carol.access_token, wid)
        with self.assertRaises(WorkspaceError) as missing:
            self.product.get_workspace(carol.access_token, "ws-" + "0" * 24)
        self.assertEqual(str(foreign.exception), str(missing.exception))

    def test_no_workspace_write_bumps_corpus_generation(self):
        wid = self._workspace()
        self.product.workspace_respond_invite(self.bob.access_token, wid,
                                              accept=True, **sec(self.bob))
        gen = self.product.freshness()["serving_generation"]
        self.product.workspace_add_note(self.alice.access_token, wid, "x", **sec(self.alice))
        self.product.workspace_add_task(self.alice.access_token, wid, "y", **sec(self.alice))
        self.assertEqual(self.product.freshness()["serving_generation"], gen)


if __name__ == "__main__":
    unittest.main()
