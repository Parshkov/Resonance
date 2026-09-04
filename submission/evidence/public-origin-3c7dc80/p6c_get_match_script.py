import json, sys, datetime, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ["NONCE"]="x"
from p5b_reservation import Client, BASE, now
THOUGHT = {"topic": "Panic buying after a shortage rumour", "domain": "consumer-economics",
           "nodes": [{"id": "b0", "label": "supply shortage rumour", "role": "problem"}, {"id": "b1", "label": "synchronized bulk purchases", "role": "mechanism"},
                     {"id": "b2", "label": "demand amplification", "role": "state"}, {"id": "b3", "label": "empty shelves", "role": "outcome"}, {"id": "b5", "label": "staggered restocking", "role": "method"}],
           "relations": [{"source": "b0", "target": "b1", "type": "causes"}, {"source": "b1", "target": "b2", "type": "causes"}, {"source": "b2", "target": "b3", "type": "causes"}, {"source": "b3", "target": "b1", "type": "causes"}, {"source": "b5", "target": "b2", "type": "prevents"}]}
c=Client(); c.guest()
st,p=c.request("POST","/api/webmcp/prepare",{"request_id":"gm-1","thought":THOUGHT}); print(f"| {now()} | prepare | {st} | input_kind={p.get('input_kind')} |")
st,pv=c.request("GET","/api/webmcp/preview")
st,sh=c.request("POST","/api/webmcp/share",{"request_id":"gm-2","confirm":True,"confirmation_token":pv.get("confirmation_token")}); print(f"| {now()} | share | {st} | shared={sh.get('shared')} |")
st,dl=c.request("GET","/api/webmcp/discover?source=live"); ms=dl.get("matches_in_backend_order",[]); print(f"| {now()} | GET /api/webmcp/discover?source=live | {st} | n={len(ms)} result_id={'set' if dl.get('result_id') else None} first_session={ms[0].get('session_id') if ms else None} |")
for i in range(min(3,len(ms))):
    sid=ms[i].get("session_id"); st,gm=c.request("GET",f"/api/webmcp/match?result_id={dl.get('result_id')}&session_id={sid}")
    print(f"| {now()} | GET /api/webmcp/match (match #{i+1}, session={sid}) | {st} | {json.dumps({k:gm.get(k) for k in ('error','message','source') if k in gm} or {'keys':sorted(gm.keys())})[:220]} |")
st,dl2=c.request("GET","/api/webmcp/discover?source=live"); print(f"| {now()} | GET discover again | {st} | same_result_id={dl2.get('result_id')==dl.get('result_id')} n={len(dl2.get('matches_in_backend_order',[]))} |")
sid=(dl2.get("matches_in_backend_order") or [{}])[0].get("session_id"); st,gm=c.request("GET",f"/api/webmcp/match?result_id={dl2.get('result_id')}&session_id={sid}")
print(f"| {now()} | GET /api/webmcp/match immediately after 2nd discover | {st} | {json.dumps({k:gm.get(k) for k in ('error','message','source') if k in gm} or {'keys':sorted(gm.keys())})[:220]} |")
st,cs=c.request("POST","/api/webmcp/consent",{"request_id":"gm-3","shared":False}); print(f"| {now()} | consent shared=false | {st} | revoked={cs.get('revoked')} |")
