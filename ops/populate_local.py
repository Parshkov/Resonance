"""Fill a LOCAL Resonance with several people, so the product can be judged.

Most of what Resonance does needs more than one person: a match, an
introduction, a conversation, a shared topic. On an empty instance every one of
those sections is correctly absent, which is indistinguishable from broken --
and that ambiguity is what let real defects sit unnoticed. Walking the site on
a populated instance found, in one pass, an introduction that declined itself
by default and engine identifiers printed to people.

    python3 -m src.product.web_server --db :memory: --host 127.0.0.1 \
        --port 8830 --origin http://127.0.0.1:8830 &
    python3 ops/populate_local.py http://127.0.0.1:8830 /tmp/people.json

Then open the origin in a browser, share a thought, and the other people are
already there to match. `act.py`-style follow-ups (accepting an introduction,
replying) run through `act()` below with the saved credentials.

The base URL must match the server's --origin exactly: the Origin header it
sends is the base you give it, and 127.0.0.1 is a different origin from
localhost however identical they look. A mismatch fails every share with
csrf_rejected, which reads like a bug in sharing and is not one.

LOCAL ONLY. It creates pseudonymous guest accounts, which a deployment with
sign-in refuses outright -- as it should. Never point this at production.

One local hazard worth knowing, because it wastes an hour: cookies are scoped
per host, not per port. Two instances on 127.0.0.1 in one browser overwrite
each other's session, and the second reads as "you are signed out" or as an
empty account.
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

SHAPE = {"nodes": [("pressure to ship", "problem"), ("skipped review", "mechanism"),
                   ("rework", "outcome"), ("jittered backoff", "method")],
         "relations": [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")]}
SOIL = {"nodes": [("over-fertilising", "problem"), ("salt accumulation", "mechanism"),
                  ("root damage", "outcome"), ("leaching schedule", "method")],
        "relations": [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")]}
CLINIC = {"nodes": [("waiting-list pressure", "problem"), ("skipped triage", "mechanism"),
                    ("readmission", "outcome"), ("nurse callback", "method")],
          "relations": [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")]}


def thought(topic: str, domain: str, spec: dict) -> dict:
    return {
        "topic": topic, "domain": domain,
        "nodes": [{"id": f"n{i}", "label": label, "role": role}
                  for i, (label, role) in enumerate(spec["nodes"])],
        "relations": [{"source": f"n{a}", "target": f"n{b}", "type": kind}
                      for a, b, kind in spec["relations"]],
    }


def person(base: str, name: str) -> dict:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    csrf = {"token": ""}

    def call(method: str, path: str, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "Origin": base}
        if csrf["token"]:
            headers["X-Resonance-CSRF"] = csrf["token"]
        request = urllib.request.Request(base + path, data=data, method=method,
                                         headers=headers)
        try:
            with opener.open(request, timeout=20) as response:
                body = response.read().decode()
                return response.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode() or "{}")

    status, creds = call("POST", "/api/product/guest", {})
    if status != 200:
        raise SystemExit(f"{name}: this deployment refuses guest accounts ({status}). "
                         "populate_local.py is for a local instance only.")
    csrf["token"] = creds.get("csrf_token", "")
    return {"name": name, "call": call, "jar": jar,
            "csrf": csrf["token"], "user_id": creds.get("user_id")}


def share(who: dict, what: dict, location: dict | None = None):
    payload = {"request_id": f"{who['name']}-1", "authorship": "their_own_words",
               "thought": what}
    if location:
        payload["coarse_location"] = location
    status, prepared = who["call"]("POST", "/api/webmcp/prepare", payload)
    if status != 200:
        return status, prepared
    _, preview = who["call"]("GET", "/api/webmcp/preview")
    return who["call"]("POST", "/api/webmcp/share",
                       {"request_id": f"{who['name']}-2", "confirm": True,
                        "confirmation_token": preview.get("confirmation_token", "")})


def act(base: str, saved: dict, method: str, path: str, payload=None):
    """One call as a previously created person, from the saved credentials."""
    cookie = "; ".join(f"{name}={value}" for name, value in saved["cookies"])
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json", "Origin": base,
                 "Cookie": cookie, "X-Resonance-CSRF": saved["csrf"]})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode()
            return response.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


CAST = (
    ("bea", thought("Salt builds up under heavy fertilising", "agriculture", SOIL),
     {"city": "Lisbon", "region": "Lisboa", "lat": 38.7, "lon": -9.1}),
    ("cai", thought("Triage skipped under waiting-list pressure", "healthcare", CLINIC),
     {"city": "Berlin", "region": "Berlin", "lat": 52.5, "lon": 13.4}),
    ("dov", thought("Retry storms after a partial outage", "distributed-systems", SHAPE),
     {"city": "Tallinn", "region": "Harju", "lat": 59.4, "lon": 24.8}),
)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8830"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/people.json"
    if "resonance.parshkov.com" in base:
        raise SystemExit("refusing: this creates accounts, and production is for "
                         "real people who signed in.")
    people = {}
    for name, what, location in CAST:
        who = person(base, name)
        people[name] = who
        status, answer = share(who, what, location)
        print(f"{name}: {status} {answer.get('say') or answer}")
    json.dump({name: {"cookies": [(c.name, c.value) for c in who["jar"]],
                      "csrf": who["csrf"], "user_id": who["user_id"]}
               for name, who in people.items()}, open(out, "w"))
    print(f"credentials for later steps: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
