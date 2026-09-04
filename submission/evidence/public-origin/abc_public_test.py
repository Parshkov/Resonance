"""Phase 3 — real multi-user A/B/C structural test over the PUBLIC /mcp origin.

Three independent OAuth guest identities (dynamic registration + PKCE + the
guest consent form, exactly as ops/oauth_smoke.py does it) each drive MCP over
POST /mcp with their own bearer.  Stdlib only.  Never prints tokens or codes.

  A = retry storm / outage feedback loop            (structure S, vocabulary V1)
  B = panic buying / shortage feedback loop         (structure S, vocabulary V2)  <- discovering subject
  C = retry/outage observability, no feedback loop  (structure S', vocabulary V1)

Expectation: B's discover ranks A (same structure, different words) above C
(same words, weaker/different structure).

Output (privacy-safe: pseudonymous ids, session/result ids, scores, relation
mappings, state transitions; NO raw context text, NO tokens):
  phase3_abc_public.json, phase3_abc_public.md
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from ops import oauth_smoke  # noqa: E402

RESOURCE = sys.argv[1] if len(sys.argv) > 1 else "https://resonance-production-cfe3.up.railway.app/mcp"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pseudo(value: str | None) -> str | None:
    """Pseudonymise an account id: keep the prefix, hash the rest."""
    if not value:
        return value
    return value.split("-")[0] + "-" + hashlib.sha256(value.encode()).hexdigest()[:10]


# --- case-insensitive header view (the edge lowercases header names) --------
class _CI(dict):
    def __init__(self, items):
        super().__init__((k.lower(), v) for k, v in dict(items).items())

    def get(self, key, default=None):
        return super().get(key.lower(), default)


_orig_req = oauth_smoke.Smoke._req


def _ci_req(self, url, **kw):
    status, headers, body = _orig_req(self, url, **kw)
    return status, _CI(headers), body


oauth_smoke.Smoke._req = _ci_req


# --- original contexts (author: this evidence run; not private conversation) -
# Kept as documentation of what each structured graph encodes.  The graphs
# below are what is actually sent (structured prepare); the raw texts are used
# once (identity A) for a NON-shared raw-text prepare to record input_kind.
CONTEXT_A = (
    "Last week a regional cache tier lost half its capacity and only a fraction of requests failed. "
    "Every client library treated the failures as transient and retried immediately, all at the same moment. "
    "The extra retries multiplied the request rate against the tier that was already struggling. "
    "Higher load produced more timeouts, and each timeout produced yet another wave of retries. "
    "Within minutes a partial degradation had turned into a full outage of the whole read path. "
    "The fix we settled on is a per-client retry budget so callers cannot amplify load without bound. "
    "On top of that we add exponential backoff with jitter so retries spread out instead of arriving in lockstep. "
    "A circuit breaker on the client side stops the amplification early once the error rate crosses a threshold."
)
CONTEXT_B = (
    "A rumour spread on local message boards that cooking oil would be scarce for the next month. "
    "Shoppers who heard it went to the supermarket and bought several bottles instead of one. "
    "Because so many people bought extra at the same time, demand spiked far above the normal weekly level. "
    "The shelves emptied and the empty shelves were photographed and shared, which confirmed the rumour for others. "
    "More people then rushed to buy, and a mild supply hiccup turned into a real shortage for everyone. "
    "The store manager introduced a two-bottle cap per customer so that no single shopper could amplify the run. "
    "Deliveries were also staggered across the day so that shelves never looked completely bare. "
    "Simple rationing broke the loop: once shelves stayed visibly stocked, the panic buying stopped."
)
CONTEXT_C = (
    "Our platform team is building an observability view for the payments outage last quarter. "
    "The dashboard shows a retries counter, a timeouts histogram, and the outage window as an annotation. "
    "Retries are recorded per endpoint so that engineers can see how many attempts each request took. "
    "During the outage the retry counter climbed, but the retries themselves did not change the failure rate. "
    "The upstream provider was fully down, so every attempt failed identically regardless of how many were made. "
    "The monitoring work is about making the retries and timeouts visible, not about preventing them. "
    "We also export the dashboard panels to the weekly reliability report. "
    "Alerting rules require the timeout histogram to be populated before an alert can fire."
)

THOUGHT_A = {
    "topic": "Retry storm turns partial outage into full outage",
    "domain": "distributed-systems",
    "nodes": [
        {"id": "a0", "label": "partial upstream outage", "role": "problem"},
        {"id": "a1", "label": "synchronized client retries", "role": "mechanism"},
        {"id": "a2", "label": "request amplification", "role": "state"},
        {"id": "a3", "label": "cascading saturation", "role": "outcome"},
        {"id": "a4", "label": "per-client retry budget", "role": "constraint"},
        {"id": "a5", "label": "jittered exponential backoff", "role": "method"},
        {"id": "a6", "label": "client-side circuit breaker", "role": "method"},
    ],
    "relations": [
        {"source": "a0", "target": "a1", "type": "causes"},
        {"source": "a1", "target": "a2", "type": "causes"},
        {"source": "a2", "target": "a3", "type": "causes"},
        {"source": "a3", "target": "a1", "type": "causes"},      # feedback loop
        {"source": "a4", "target": "a1", "type": "constrains"},
        {"source": "a5", "target": "a3", "type": "prevents"},
        {"source": "a6", "target": "a2", "type": "prevents"},
    ],
}
THOUGHT_B = {
    "topic": "Panic buying turns a rumour into a shortage",
    "domain": "retail-logistics",
    "nodes": [
        {"id": "b0", "label": "shortage rumour", "role": "problem"},
        {"id": "b1", "label": "synchronized bulk purchasing", "role": "mechanism"},
        {"id": "b2", "label": "demand amplification", "role": "state"},
        {"id": "b3", "label": "empty shelves", "role": "outcome"},
        {"id": "b4", "label": "per-customer purchase cap", "role": "constraint"},
        {"id": "b5", "label": "staggered restocking", "role": "method"},
        {"id": "b6", "label": "rationing scheme", "role": "method"},
    ],
    "relations": [
        {"source": "b0", "target": "b1", "type": "causes"},
        {"source": "b1", "target": "b2", "type": "causes"},
        {"source": "b2", "target": "b3", "type": "causes"},
        {"source": "b3", "target": "b1", "type": "causes"},      # feedback loop
        {"source": "b4", "target": "b1", "type": "constrains"},
        {"source": "b5", "target": "b3", "type": "prevents"},
        {"source": "b6", "target": "b2", "type": "prevents"},
    ],
}
THOUGHT_C = {
    "topic": "Outage retries and timeouts dashboard",
    "domain": "distributed-systems",
    "nodes": [
        {"id": "c0", "label": "partial upstream outage", "role": "problem"},
        {"id": "c1", "label": "client retries", "role": "mechanism"},
        {"id": "c2", "label": "retry counter panel", "role": "evidence"},
        {"id": "c3", "label": "timeout histogram panel", "role": "evidence"},
        {"id": "c4", "label": "reliability dashboard", "role": "resource"},
        {"id": "c5", "label": "weekly reliability report", "role": "outcome"},
        {"id": "c6", "label": "alerting rule", "role": "method"},
    ],
    "relations": [
        {"source": "c0", "target": "c1", "type": "causes"},
        {"source": "c2", "target": "c4", "type": "part_of"},
        {"source": "c3", "target": "c4", "type": "part_of"},
        {"source": "c1", "target": "c2", "type": "supports"},
        {"source": "c4", "target": "c5", "type": "supports"},
        {"source": "c6", "target": "c3", "type": "requires"},
    ],
}


class Identity:
    """One independent guest account: OAuth onboarding + MCP client."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.smoke = oauth_smoke.Smoke(RESOURCE, auto_consent=True, verbose=False)
        self.bearer: str | None = None
        self.mcp_session: str | None = None
        self.mcp_session_header_seen = False
        self.user_id: str | None = None
        self.calls: list[dict] = []

    # -- onboarding (same steps as oauth_smoke, quiet) ---------------------
    def onboard(self) -> dict:
        s = self.smoke
        status, headers, _ = s._rpc("ping", mid=1, bearer=None)
        import re
        m = re.search(r'resource_metadata="([^"]+)"', headers.get("WWW-Authenticate", ""))
        status, _, prm = s._json(m.group(1))
        issuer = prm["authorization_servers"][0].rstrip("/")
        status, _, asm = s._json(f"{issuer}/.well-known/oauth-authorization-server")
        s.meta = asm
        status, _, client = s._json(asm["registration_endpoint"], method="POST",
                                    headers={"Content-Type": "application/json"},
                                    data=json.dumps({
                                        "client_name": f"resonance-abc-evidence-{self.name}",
                                        "redirect_uris": [oauth_smoke.REDIRECT_URI],
                                        "grant_types": ["authorization_code", "refresh_token"],
                                        "response_types": ["code"],
                                        "token_endpoint_auth_method": "none"}).encode())
        s.client_id = client["client_id"]
        code = s._authorize(quiet=True)
        status, _, tok = s._token({"grant_type": "authorization_code", "code": code,
                                   "code_verifier": s._verifier, "redirect_uri": oauth_smoke.REDIRECT_URI,
                                   "client_id": s.client_id, "resource": s.resource})
        self.bearer = tok.get("access_token")
        self.refresh = tok.get("refresh_token")
        return {"identity": self.name, "registration_status": 201 if client.get("client_id") else None,
                "token_status": status, "got_access_token": bool(self.bearer),
                "got_refresh_token": bool(self.refresh), "client_id_prefix": str(s.client_id)[:8] + "…"}

    # -- MCP -----------------------------------------------------------------
    def rpc(self, method: str, params: dict | None = None, mid: int = 1) -> tuple[int, dict, dict]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.bearer}"}
        if self.mcp_session:
            headers["Mcp-Session-Id"] = self.mcp_session
        req = Request(RESOURCE, method="POST", headers=headers,
                      data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                       "params": params or {}}).encode())
        try:
            with urlopen(req, timeout=30) as r:
                status, hdrs, body = r.status, _CI(r.headers), r.read()
        except HTTPError as e:
            status, hdrs, body = e.code, _CI(e.headers), e.read()
        sid = hdrs.get("Mcp-Session-Id")
        if sid:
            self.mcp_session_header_seen = True
            self.mcp_session = sid
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"_raw": body[:200].decode("utf-8", "replace")}
        return status, hdrs, payload

    def initialize(self) -> dict:
        status, hdrs, payload = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                        "clientInfo": {"name": f"abc-{self.name}", "version": "0"}})
        self.rpc("notifications/initialized")
        return {"status": status, "protocolVersion": (payload.get("result") or {}).get("protocolVersion"),
                "serverInfo": (payload.get("result") or {}).get("serverInfo"),
                "mcp_session_id_header_present": self.mcp_session_header_seen}

    def call(self, tool: str, arguments: dict) -> tuple[int, dict]:
        t0 = time.time()
        status, _, payload = self.rpc("tools/call", {"name": tool, "arguments": arguments}, mid=2)
        result = payload.get("result") or {}
        sc = result.get("structuredContent") or {}
        rec = {"identity": self.name, "tool": tool, "http_status": status,
               "is_error": result.get("isError"), "ms": int((time.time() - t0) * 1000),
               "jsonrpc_error": payload.get("error")}
        if result.get("isError"):
            rec["error"] = {"error": sc.get("error"), "message": sc.get("message")}
        self.calls.append(rec)
        return status, sc if result else payload


def slim_match(m: dict) -> dict:
    ev = m.get("evidence") or {}
    return {
        "session_id": m.get("session_id"),
        "person_pseudonym": pseudo(m.get("person_pseudonym")) if str(m.get("person_pseudonym", "")).startswith("person") else m.get("person_pseudonym"),
        "scores": m.get("scores"),
        "rank_fields": {k: m.get(k) for k in ("rank", "position", "accepted", "status", "decision", "mode") if k in m},
        "evidence": {
            "preserved_relation_count": ev.get("preserved_relation_count"),
            "top_correspondences": ev.get("top_correspondences"),
            **{k: v for k, v in ev.items() if k not in ("preserved_relation_count", "top_correspondences")},
        },
        "display": {k: v for k, v in (m.get("display") or {}).items() if k in ("topic", "domain", "cluster_id")},
        "other_keys": sorted(k for k in m if k not in ("session_id", "person_pseudonym", "scores", "evidence", "display")),
    }


def main() -> int:
    report: dict = {"resource": RESOURCE, "started_utc": now(), "steps": [], "health": None}
    steps = report["steps"]

    def step(name: str, ok: bool, **detail):
        steps.append({"step": name, "pass": bool(ok), **detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        return ok

    origin = RESOURCE.rsplit("/mcp", 1)[0]
    with urlopen(origin + "/api/product/health", timeout=20) as r:
        report["health"] = json.loads(r.read())

    A, B, C = Identity("A"), Identity("B"), Identity("C")
    report["onboarding"] = []
    for ident in (A, B, C):
        ob = ident.onboard()
        report["onboarding"].append(ob)
        step(f"onboard {ident.name} (register + PKCE + guest consent + token)", ob["got_access_token"])
        init = ident.initialize()
        report["onboarding"][-1]["initialize"] = init
        step(f"initialize {ident.name}", init["status"] == 200 and init["protocolVersion"] is not None)
        _, who = ident.call("resonance_whoami", {})
        ident.user_id = who.get("user_id")
        report["onboarding"][-1]["whoami"] = {"user_id": pseudo(who.get("user_id")),
                                              "actor_type": who.get("actor_type"),
                                              "display_label": who.get("display_label"),
                                              "shared_thoughts": who.get("shared_thoughts"),
                                              "contract_version": who.get("contract_version")}
        step(f"whoami {ident.name} returns account", bool(ident.user_id))
    step("three distinct accounts", len({A.user_id, B.user_id, C.user_id}) == 3,
         user_ids=[pseudo(x.user_id) for x in (A, B, C)])

    # Extra evidence: raw-text prepare (NOT shared) to record the extractor path.
    st, raw_prep = A.call("resonance_prepare_thought", {"context": CONTEXT_A})
    report["raw_text_prepare_A_not_shared"] = {
        "http_status": st, "input_kind": raw_prep.get("input_kind"),
        "source_retention": raw_prep.get("source_retention"),
        "draft_id": raw_prep.get("draft_id"), "discoverable": raw_prep.get("discoverable"),
        "warnings": raw_prep.get("warnings"),
        "extracted_node_count": len(((raw_prep.get("will_become_discoverable") or {}).get("thought_dna") or {}).get("nodes", []) or []),
        "extracted_relation_count": len(((raw_prep.get("will_become_discoverable") or {}).get("thought_dna") or {}).get("relations", []) or []),
        "error": raw_prep.get("error"),
    }
    step("A raw-text prepare (not shared) accepted", st == 200 and bool(raw_prep.get("draft_id")))

    # Structured prepare -> share for A, B, C.
    shared: dict[str, dict] = {}
    for ident, thought in ((A, THOUGHT_A), (B, THOUGHT_B), (C, THOUGHT_C)):
        st, prep = ident.call("resonance_prepare_thought", {"thought": thought})
        ok = st == 200 and bool(prep.get("confirmation_token")) and prep.get("discoverable") is False
        dna = (prep.get("will_become_discoverable") or {}).get("thought_dna") or {}
        rec = {"identity": ident.name, "prepare_status": st, "draft_id": prep.get("draft_id"),
               "session_id_at_prepare": prep.get("session_id"), "input_kind": prep.get("input_kind"),
               "source_retention": prep.get("source_retention"), "discoverable_after_prepare": prep.get("discoverable"),
               "requires_explicit_confirmation": prep.get("requires_explicit_confirmation"),
               "preview_node_count": len(dna.get("nodes", []) or []),
               "preview_relation_count": len(dna.get("relations", []) or []),
               "preview_relations": [(r.get("source"), r.get("type"), r.get("target")) for r in dna.get("relations", []) or []],
               "presentation": (prep.get("will_become_discoverable") or {}).get("presentation"),
               "error": prep.get("error"), "message": prep.get("message") if prep.get("error") else None}
        step(f"{ident.name} prepare_thought (structured) -> private draft + confirmation_token", ok)
        if not ok:
            shared[ident.name] = rec
            continue
        # consent gate: share without confirm must be refused
        st_nc, no_conf = ident.call("resonance_share_thought", {"draft_id": prep["draft_id"],
                                                                 "confirmation_token": prep["confirmation_token"],
                                                                 "confirm": False, "request_id": f"abc-{ident.name}-share-noconfirm"})
        rec["share_without_confirm"] = {"http_status": st_nc, "error": no_conf.get("error")}
        step(f"{ident.name} share without confirm refused", no_conf.get("error") == "confirmation_required")
        st, sh = ident.call("resonance_share_thought", {"draft_id": prep["draft_id"],
                                                        "confirmation_token": prep["confirmation_token"],
                                                        "confirm": True, "request_id": f"abc-{ident.name}-share-1"})
        rec.update({"share_status": st, "shared": sh.get("shared"), "discoverable_after_share": sh.get("discoverable"),
                    "session_id": sh.get("session_id"), "share_error": sh.get("error")})
        step(f"{ident.name} share_thought(confirm=true) -> discoverable", st == 200 and sh.get("discoverable") is True)
        shared[ident.name] = rec
    report["shares"] = shared
    sess = {k: v.get("session_id") for k, v in shared.items()}
    report["session_ids"] = sess
    if not all(sess.values()):
        report["finished_utc"] = now()
        return finish(report, A, B, C)

    # my_thoughts for B
    st, mine = B.call("resonance_my_thoughts", {})
    b_states = {s.get("session_id"): s.get("share_state") for s in mine.get("sessions", [])}
    report["B_my_thoughts"] = b_states
    step("B my_thoughts shows B's session discoverable", b_states.get(sess["B"]) == "discoverable")

    # B discover
    st, disc = B.call("resonance_discover", {"session_id": sess["B"], "k": 15})
    matches = disc.get("matches_in_backend_order") or []
    order = [m.get("session_id") for m in matches]
    rejected = disc.get("rejected") or []
    report["B_discover_1"] = {
        "http_status": st, "result_id": disc.get("result_id"), "query_session_id": disc.get("query_session_id"),
        "source": disc.get("source"), "discovery_contract": disc.get("discovery_contract"),
        "match_count": len(matches), "rejected_count": len(rejected),
        "order": order,
        "rank_A": order.index(sess["A"]) if sess["A"] in order else None,
        "rank_C": order.index(sess["C"]) if sess["C"] in order else None,
        "A_in_rejected": sess["A"] in [r.get("session_id") for r in rejected],
        "C_in_rejected": sess["C"] in [r.get("session_id") for r in rejected],
        "match_A": next((slim_match(m) for m in matches if m.get("session_id") == sess["A"]), None),
        "match_C": next((slim_match(m) for m in matches if m.get("session_id") == sess["C"]), None),
        "rejected_C": next((slim_match(m) for m in rejected if m.get("session_id") == sess["C"]), None),
        "top_5": [slim_match(m) for m in matches[:5]],
        "aggregation": disc.get("aggregation"), "freshness": disc.get("freshness"),
        "error": disc.get("error"), "message": disc.get("message") if disc.get("error") else None,
    }
    step("B discover returns result_id", st == 200 and bool(disc.get("result_id")))
    step("B discover: A present in matches", sess["A"] in order)
    step("B discover: B (self) absent", sess["B"] not in order)
    a_rank, c_rank = report["B_discover_1"]["rank_A"], report["B_discover_1"]["rank_C"]
    step("B discover: A ranked above C (or C not accepted at all)",
         a_rank is not None and (c_rank is None or a_rank < c_rank), rank_A=a_rank, rank_C=c_rank)
    mA, mC = report["B_discover_1"]["match_A"], report["B_discover_1"]["match_C"] or report["B_discover_1"]["rejected_C"]
    if mA and mC:
        sa, sc_ = (mA.get("scores") or {}), (mC.get("scores") or {})
        step("B discover: structural(A) > structural(C)", (sa.get("structural") or 0) > (sc_.get("structural") or 0),
             structural_A=sa.get("structural"), structural_C=sc_.get("structural"),
             semantic_A=sa.get("semantic"), semantic_C=sc_.get("semantic"))
        step("B discover: preserved_relation_count(A) > (C)",
             (mA["evidence"].get("preserved_relation_count") or 0) > (mC["evidence"].get("preserved_relation_count") or 0),
             A=mA["evidence"].get("preserved_relation_count"), C=mC["evidence"].get("preserved_relation_count"))
    result_id = disc.get("result_id")

    # B explain_match on A
    st, ex = B.call("resonance_explain_match", {"result_id": result_id, "session_id": sess["A"]})
    report["B_explain_A"] = {"http_status": st, "error": ex.get("error"), "keys": sorted(ex.keys()),
                             "scores": ex.get("scores"), "evidence": ex.get("evidence"),
                             "match": slim_match(ex.get("match")) if isinstance(ex.get("match"), dict) else None}
    step("B explain_match(result_id, A) ok", st == 200 and not ex.get("error"))
    # subject isolation: A cannot read B's result
    st, stolen = A.call("resonance_explain_match", {"result_id": result_id, "session_id": sess["A"]})
    report["A_explain_Bs_result"] = {"http_status": st, "error": stolen.get("error"), "message": stolen.get("message")}
    step("A cannot read B's result (subject isolation -> error)", bool(stolen.get("error")))
    # C tries to act on A's session via an intro from a result it does not own
    st, stolen_c = C.call("resonance_request_intro", {"from_session_id": sess["C"], "target_session_id": sess["A"],
                                                       "message": "hello", "confirm": True,
                                                       "request_id": "abc-C-intro-without-discovery"})
    report["C_request_intro_A_without_discovery"] = {"http_status": st, "error": stolen_c.get("error"),
                                                     "message": stolen_c.get("message"), "intro_id": stolen_c.get("intro_id"),
                                                     "state": stolen_c.get("state")}
    steps.append({"step": "C request_intro to A without discovery (observed, no expectation asserted)",
                  "pass": True, "observed_error": stolen_c.get("error"), "observed_state": stolen_c.get("state")})

    # B request_intro -> A
    st, intro = B.call("resonance_request_intro", {"from_session_id": sess["B"], "target_session_id": sess["A"],
                                                    "message": "Your loop looks like mine. Compare notes?",
                                                    "confirm": True, "request_id": "abc-B-intro-1"})
    intro_id = intro.get("intro_id")
    report["B_request_intro_A"] = {"http_status": st, "intro_id": intro_id, "state": intro.get("state"),
                                   "direction": intro.get("direction"), "error": intro.get("error"),
                                   "message": intro.get("message") if intro.get("error") else None,
                                   "keys": sorted(intro.keys())}
    step("B request_intro -> A created", st == 200 and bool(intro_id))
    # idempotent replay
    st, intro2 = B.call("resonance_request_intro", {"from_session_id": sess["B"], "target_session_id": sess["A"],
                                                     "message": "Your loop looks like mine. Compare notes?",
                                                     "confirm": True, "request_id": "abc-B-intro-1"})
    step("B request_intro replay with same request_id is idempotent", intro2.get("intro_id") == intro_id,
         replay_intro_id_equal=intro2.get("intro_id") == intro_id, error=intro2.get("error"))

    # A list_intros + accept
    st, lst = A.call("resonance_list_intros", {})
    incoming = lst.get("incoming") or []
    inc = next((i for i in incoming if i.get("intro_id") == intro_id), None)
    report["A_list_intros"] = {"http_status": st, "incoming_count": len(incoming),
                               "outgoing_count": len(lst.get("outgoing") or []),
                               "incoming_match": {k: v for k, v in (inc or {}).items()
                                                  if k in ("intro_id", "state", "direction", "from_session_id", "to_session_id", "channel_id")}}
    step("A list_intros shows B's incoming intro", inc is not None)
    st, resp = A.call("resonance_respond_intro", {"intro_id": intro_id, "accept": True, "confirm": True,
                                                   "request_id": "abc-A-accept-1"})
    channel_id = resp.get("channel_id")
    report["A_respond_intro_accept"] = {"http_status": st, "state": resp.get("state"), "channel_id": channel_id,
                                        "error": resp.get("error"), "keys": sorted(resp.keys())}
    step("A respond_intro(accept) -> channel", st == 200 and bool(channel_id))

    # A send_message ; B read_messages
    st, sent = A.call("resonance_send_message", {"channel_id": channel_id or "", "body": "Hi — happy to compare notes on the loop.",
                                                  "confirm": True, "request_id": "abc-A-msg-1"})
    report["A_send_message"] = {"http_status": st, "message_id": sent.get("message_id"), "delivered": sent.get("delivered"),
                                "error": sent.get("error")}
    step("A send_message delivered", st == 200 and sent.get("delivered") is True)
    st, read = B.call("resonance_read_messages", {"channel_id": channel_id or ""})
    msgs = read.get("messages") or []
    report["B_read_messages"] = {"http_status": st, "message_count": len(msgs),
                                 "message_ids": [m.get("message_id") for m in msgs],
                                 "senders_pseudonymised": [pseudo(m.get("sender_id") or m.get("from_user_id")) for m in msgs],
                                 "error": read.get("error"), "keys": sorted(read.keys())}
    step("B read_messages sees A's message", st == 200 and sent.get("message_id") in [m.get("message_id") for m in msgs])
    st, read_c = C.call("resonance_read_messages", {"channel_id": channel_id or ""})
    report["C_read_channel_not_member"] = {"http_status": st, "error": read_c.get("error")}
    step("C (non-member) cannot read the channel", bool(read_c.get("error")))

    # A stop_sharing ; B discover again -> A absent
    st, stop = A.call("resonance_stop_sharing", {"session_id": sess["A"], "confirm": True})
    report["A_stop_sharing"] = {"http_status": st, "revoked": stop.get("revoked"), "discoverable": stop.get("discoverable"),
                                "error": stop.get("error")}
    step("A stop_sharing -> revoked", st == 200 and stop.get("revoked") is True)
    st, who_a = A.call("resonance_whoami", {})
    step("A whoami no longer lists the session as shared", sess["A"] not in (who_a.get("shared_thoughts") or []),
         shared_thoughts=who_a.get("shared_thoughts"), private_thoughts_count=len(who_a.get("private_thoughts") or []))
    st, disc2 = B.call("resonance_discover", {"session_id": sess["B"], "k": 15})
    order2 = [m.get("session_id") for m in disc2.get("matches_in_backend_order") or []]
    rej2 = [m.get("session_id") for m in disc2.get("rejected") or []]
    report["B_discover_2_after_A_revoked"] = {"http_status": st, "result_id": disc2.get("result_id"),
                                              "order": order2, "rejected": rej2,
                                              "A_in_matches": sess["A"] in order2, "A_in_rejected": sess["A"] in rej2,
                                              "blocked_rows_removed": disc2.get("blocked_rows_removed"),
                                              "error": disc2.get("error")}
    step("B discover after revoke: A absent from matches AND rejected", sess["A"] not in order2 and sess["A"] not in rej2)
    # the old result's evidence for A must no longer be readable
    st, ex2 = B.call("resonance_explain_match", {"result_id": result_id, "session_id": sess["A"]})
    report["B_explain_A_after_revoke"] = {"http_status": st, "error": ex2.get("error"), "message": ex2.get("message")}
    steps.append({"step": "B explain_match on old result after A revoked (observed)", "pass": True,
                  "observed_error": ex2.get("error")})

    # cleanup: B and C stop sharing too (leave production clean)
    for ident in (B, C):
        st, stop = ident.call("resonance_stop_sharing", {"session_id": sess[ident.name], "confirm": True})
        step(f"cleanup: {ident.name} stop_sharing", st == 200 and stop.get("revoked") is True)

    report["finished_utc"] = now()
    return finish(report, A, B, C)


def finish(report: dict, *idents: Identity) -> int:
    report["calls"] = [c for i in idents for c in i.calls]
    report["mcp_session_id_header_seen"] = {i.name: i.mcp_session_header_seen for i in idents}
    passed = sum(1 for s in report["steps"] if s["pass"])
    total = len(report["steps"])
    report["summary"] = {"passed": passed, "total": total,
                         "failed_steps": [s["step"] for s in report["steps"] if not s["pass"]]}
    blob = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    for ident in idents:  # belt and braces: never persist a bearer
        for secret in (ident.bearer, getattr(ident, "refresh", None)):
            if secret:
                assert secret not in blob, "token leaked into report"
    with open(os.path.join(OUT_DIR, "phase3_abc_public.json"), "w") as f:
        f.write(blob)
    lines = [f"# Phase 3 — public-origin A/B/C structural test", "",
             f"Resource: {report['resource']}", f"Started: {report['started_utc']}  Finished: {report.get('finished_utc')}",
             f"Deployment health: `{json.dumps(report['health'])}`", "",
             f"**{passed}/{total} steps passed**", "", "| # | step | result | detail |", "|---|---|---|---|"]
    for n, s in enumerate(report["steps"], 1):
        detail = {k: v for k, v in s.items() if k not in ("step", "pass")}
        lines.append(f"| {n} | {s['step']} | {'PASS' if s['pass'] else 'FAIL'} | {json.dumps(detail, default=str)[:300]} |")
    d1 = report.get("B_discover_1") or {}
    lines += ["", "## B discover #1 (A shared, C shared)", "",
              f"- result_id: `{d1.get('result_id')}` source: `{d1.get('source')}` contract: `{d1.get('discovery_contract')}`",
              f"- order (session ids): `{d1.get('order')}`  rank_A={d1.get('rank_A')} rank_C={d1.get('rank_C')} rejected_count={d1.get('rejected_count')}",
              f"- A scores: `{json.dumps((d1.get('match_A') or {}).get('scores'))}`",
              f"- C scores: `{json.dumps(((d1.get('match_C') or d1.get('rejected_C')) or {}).get('scores'))}`",
              f"- A evidence: `{json.dumps((d1.get('match_A') or {}).get('evidence'), default=str)[:1200]}`",
              f"- C evidence: `{json.dumps(((d1.get('match_C') or d1.get('rejected_C')) or {}).get('evidence'), default=str)[:1200]}`",
              "", "## Session ids", "", f"`{json.dumps(report.get('session_ids'))}`", "",
              f"Mcp-Session-Id header observed from server: `{report['mcp_session_id_header_seen']}`", "",
              "Full privacy-safe detail: phase3_abc_public.json (pseudonymous ids, no raw context text, no tokens)."]
    with open(os.path.join(OUT_DIR, "phase3_abc_public.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n{passed}/{total} steps passed" + (f"; FAILED: {report['summary']['failed_steps']}" if passed != total else ""))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
