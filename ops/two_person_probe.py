"""Prove the whole loop, as two people, against a running server.

Unit tests cover each step of Resonance in isolation. What nobody had checked
in one run is the thing the product actually promises:

    one person shares and finds nobody -> a second person arrives ->
    the FIRST person is told -> they ask for an introduction ->
    the second agrees -> they talk.

Every one of those steps involves two accounts and the passage of time between
them, which is exactly what a single-account test cannot see. This walks it end
to end over plain HTTP and prints a transcript, so "ready for other people to
try" is something observed rather than assumed.

    python3 ops/two_person_probe.py                      # against a local server
    python3 ops/two_person_probe.py --origin https://…   # against a deployment

Against a deployment with sign-in configured, account creation is refused by
design and the probe says so instead of pretending: there, two real people are
the only way to run this.

Exits non-zero on the first broken promise. Prints pseudonyms, ids and scores;
never a token.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TIMEOUT = 20

ALICE_THOUGHT = {
    "topic": "A team gets slower the harder it is pushed",
    "domain": "organisations",
    "nodes": [
        {"id": "n0", "label": "delivery pressure", "role": "problem"},
        {"id": "n1", "label": "skipped review", "role": "mechanism"},
        {"id": "n2", "label": "rework", "role": "outcome"},
        {"id": "n3", "label": "slack time", "role": "method"},
    ],
    "relations": [
        {"source": "n0", "target": "n1", "type": "causes"},
        {"source": "n1", "target": "n2", "type": "causes"},
        {"source": "n3", "target": "n1", "type": "prevents"},
    ],
}

# Same shape, different world: the effort meant to help is what does the damage.
BOB_THOUGHT = {
    "topic": "Soil gives less the more it is fertilised",
    "domain": "agriculture",
    "nodes": [
        {"id": "m0", "label": "yield pressure", "role": "problem"},
        {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
        {"id": "m2", "label": "root damage", "role": "outcome"},
        {"id": "m3", "label": "fallow season", "role": "method"},
    ],
    "relations": [
        {"source": "m0", "target": "m1", "type": "causes"},
        {"source": "m1", "target": "m2", "type": "causes"},
        {"source": "m3", "target": "m1", "type": "prevents"},
    ],
}


class Failure(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f"FAILED: {message}")


class Person:
    """One participant, holding their own cookie and CSRF token."""

    def __init__(self, base: str, name: str) -> None:
        self.base = base.rstrip("/")
        self.name = name
        self.cookie: str | None = None
        self.csrf: str | None = None
        self.pseudonym = ""
        self.session_id = ""

    def call(self, method: str, path: str, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read().decode()
                cookie = response.headers.get("Set-Cookie")
                if cookie:
                    morsel = SimpleCookie(cookie).get("resonance_token")
                    if morsel is not None and morsel.value:
                        self.cookie = f"resonance_token={morsel.value}"
                return response.status, json.loads(raw or "{}")
        except HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read().decode() or "{}")
            except Exception:  # noqa: BLE001
                return exc.code, {}

    def join(self) -> None:
        status, payload = self.call("POST", "/api/product/guest", {})
        if status == 403 and payload.get("error") == "sign_in_required":
            raise SystemExit(
                "This deployment requires a real sign-in, so accounts cannot be "
                "created from a script — which is the point of it. Run this probe "
                "against a local server, or walk the same steps with two real "
                "people signed in through the site.")
        if status != 200:
            raise Failure(f"{self.name} could not join: {status} {payload}")
        self.csrf = payload["csrf_token"]
        _, state = self.call("GET", "/api/product/state")
        self.pseudonym = (state.get("account") or {}).get("display_label", "")

    def share(self, thought, tag: str) -> str:
        status, prepared = self.call("POST", "/api/webmcp/prepare",
                                     {"request_id": f"{tag}-prepare", "thought": thought})
        if status != 200:
            raise Failure(f"{self.name} could not prepare: {status} {prepared}")
        status, preview = self.call("GET", "/api/webmcp/preview")
        if status != 200 or not preview.get("confirmation_token"):
            raise Failure(f"{self.name} got no preview to approve: {status} {preview}")
        status, receipt = self.call("POST", "/api/webmcp/share", {
            "request_id": f"{tag}-share", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        if status != 200:
            raise Failure(f"{self.name} could not share: {status} {receipt}")
        _, mine = self.call("GET", "/api/product/sessions")
        sessions = mine.get("sessions") or []
        if not sessions:
            raise Failure(f"{self.name} shared but owns no session")
        self.session_id = str(sessions[-1]["session_id"])
        return self.session_id


def step(number: int, text: str) -> None:
    print(f"\n{number}. {text}")


def probe(base: str) -> None:
    print(f"Resonance two-person probe against {base}")

    alice, bob = Person(base, "Alice"), Person(base, "Bob")

    step(1, "Alice joins and shares a thought into an empty world.")
    alice.join()
    alice.share(ALICE_THOUGHT, "alice")
    print(f"   Alice is {alice.pseudonym or '(no pseudonym)'}, session {alice.session_id}")

    step(2, "No PERSON matches her yet. That must be an answer, not an error.")
    status, found = alice.call(
        "GET", f"/api/product/rich_discover?session_id={alice.session_id}&k=8")
    if status != 200:
        raise Failure(f"discovery failed for Alice: {status} {found}")
    rows = found.get("matches") or []
    people = [m for m in rows if not (m.get("display") or {}).get("demo_persona")]
    print(f"   discovery returned {len(rows)} rows, {len(people)} of them people")
    if people:
        raise Failure("someone matched Alice before anyone had arrived")
    status, waiting = alice.call("GET", "/api/product/resonances")
    if status != 200 or not waiting.get("available"):
        raise Failure(f"the standing search is unavailable: {status} {waiting}")
    if waiting.get("alerts"):
        raise Failure("Alice was told about someone before anyone arrived")
    print("   nothing waiting — and a seeded demo row never becomes a resonance,")
    print("   because telling a real person about a fixture would be inventing someone")

    step(3, "Bob arrives later and shares the same shape in another field.")
    bob.join()
    bob.share(BOB_THOUGHT, "bob")
    print(f"   Bob is {bob.pseudonym or '(no pseudonym)'}, session {bob.session_id}")

    step(4, "Alice is told — the half of the product that waits.")
    alerts = []
    for _ in range(10):
        _, waiting = alice.call("GET", "/api/product/resonances")
        alerts = waiting.get("alerts") or []
        if alerts:
            break
        time.sleep(1)
    if not alerts:
        raise Failure("Bob arrived and Alice was never told")
    arrived = [a for a in alerts if a.get("reason") == "they_arrived"]
    if not arrived:
        raise Failure("Alice was told, but not that someone arrived after she shared")
    scores = arrived[0].get("scores_at_detection") or {}
    print(f"   reason={arrived[0]['reason']} structural={scores.get('structural')}")

    step(5, "Alice asks for an introduction. Nothing opens until Bob agrees.")
    status, asked = alice.call("POST", "/api/product/intro/request", {
        "from_session_id": alice.session_id, "target_session_id": bob.session_id,
        "message": "Different field, same shape — worth comparing notes?",
        "confirmed": True, "request_id": "intro-1"})
    if status != 200:
        raise Failure(f"Alice could not ask: {status} {asked}")
    _, bobs = bob.call("GET", "/api/product/intro/list")
    incoming = bobs.get("incoming") or []
    if not incoming:
        raise Failure("Bob never saw the request")
    intro_id = incoming[0]["intro_id"]
    if incoming[0].get("channel_id"):
        raise Failure("a channel opened before Bob agreed to anything")
    print(f"   Bob sees one request, state {incoming[0]['state']}, no channel yet")

    step(6, "Bob accepts, and only now does a channel exist.")
    status, accepted = bob.call("POST", "/api/product/intro/respond",
                                {"intro_id": intro_id, "accept": True,
                                 "confirmed": True, "request_id": "intro-2"})
    if status != 200:
        raise Failure(f"Bob could not accept: {status} {accepted}")
    _, bobs = bob.call("GET", "/api/product/intro/list")
    channel = next((row.get("channel_id") for row in (bobs.get("incoming") or [])
                    if row["intro_id"] == intro_id), None)
    if not channel:
        raise Failure("Bob accepted but no channel opened")
    print(f"   channel {channel}")

    step(7, "They talk.")
    status, sent = alice.call("POST", "/api/product/channel/send", {
        "channel_id": channel, "body": "Yours is soil, mine is a team. Same trap.",
        "confirmed": True, "request_id": "msg-1"})
    if status != 200:
        raise Failure(f"Alice could not send: {status} {sent}")
    status, read = bob.call("GET", f"/api/product/channel/messages?channel_id={channel}")
    bodies = [m.get("body") for m in (read.get("messages") or [])]
    if not bodies:
        raise Failure("Bob cannot read what Alice sent")
    print(f"   Bob reads: {bodies[-1]!r}")
    bob.call("POST", "/api/product/channel/send", {
        "channel_id": channel, "body": "The fix is the same too: stop pushing.",
        "confirmed": True, "request_id": "msg-2"})
    _, back = alice.call("GET", f"/api/product/channel/messages?channel_id={channel}")
    if len(back.get("messages") or []) < 2:
        raise Failure("Alice cannot read Bob's reply")
    print(f"   Alice reads: {back['messages'][-1].get('body')!r}")

    step(8, "Alice withdraws, and the finding stops being reported.")
    alice.call("POST", "/api/product/revoke",
               {"session_id": alice.session_id, "confirmed": True,
                "request_id": "revoke-1"})
    _, waiting = alice.call("GET", "/api/product/resonances", )
    if waiting.get("alerts"):
        raise Failure("Alice revoked her thought and is still being told about it")
    print("   nothing reported after the withdrawal")

    print("\nThe whole loop holds: shared, waited, told, asked, agreed, talked, withdrew.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8799",
                        help="origin of a running Resonance server")
    args = parser.parse_args()
    try:
        probe(args.origin)
    except Failure as failure:
        print(f"\n{failure}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
