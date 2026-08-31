"""
E1 -- the decisive experiment specified by the R0-B comparative review
(research/reviews/R0_B_fingerprint_retrieval_review_*.md).

Question: does the FULL converged B1/B2 machinery (landmark descriptors,
typed-path fingerprints, distance buckets, df cutoff, idf weighting,
correspondence-consensus scoring) separate a full-constellation cross-domain
analog from bare-chain generic-motif distractors -- the case R0-H's toy
(bag of role-paths, no descriptors, no consensus, 3-chain graphs) could not?

Two filler worlds operationalize the B2-vs-H disagreement about real corpora:
  world R ("rich")   : random typed graphs, varied motifs
  world Z ("zipfian"): 80% bare causal chains (H's motif-poor world)

Three descriptor variants resolve review disagreement D2:
  D0    : role-only landmark descriptors (B2 style)
  D1    : one-round directed typed WL labels (B1 style)
  MULTI : both scales indexed together (B1's full design)

Kill rule (from the review): if the noisy cross-domain analog does not outrank
every bare-chain distractor with the full machinery ON, H's NO-GO stands and
the structural channel demotes to verification-only.

stdlib only; deterministic; run: python3 R0_E1_fingerprint_discrimination.py
"""
import hashlib, random, math, time
from collections import defaultdict, Counter

ROLES = ["entity", "process", "state", "outcome", "quantity", "condition", "agent"]
RELS  = ["causes", "increases", "prevents", "enables", "requires", "precedes"]

class G:
    def __init__(self, name, roles, edges):
        self.name, self.roles, self.edges = name, list(roles), list(edges)
        self.n = len(roles)
        self.adj = defaultdict(list)              # undirected traversal view
        for (u, v, r) in edges:
            self.adj[u].append((v, r, "+"))       # + = along edge direction
            self.adj[v].append((u, r, "-"))       # - = against it

def h64(*parts):
    return hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=8).hexdigest()

# ---------------------------------------------------------------- descriptors
def d0(g):
    return {v: g.roles[v] for v in range(g.n)}

def d1(g):
    base = d0(g)
    out = {}
    for v in range(g.n):
        nb = sorted((dirn, rel, base[u]) for (u, rel, dirn) in g.adj[v])
        out[v] = h64("wl", base[v], *nb)
    return out

# --------------------------------------------------------------- fingerprints
def pathsig(g, a, b, maxlen=3):
    """shortest undirected path <=maxlen; token = (direction, relation) per step"""
    prev = {a: None}
    frontier = [a]
    depth = 0
    while frontier and depth < maxlen:
        depth += 1
        nxt = []
        for u in frontier:
            for (w, rel, dirn) in g.adj[u]:
                if w not in prev:
                    prev[w] = (u, rel, dirn)
                    nxt.append(w)
        if b in prev and prev[b] is not None:
            break
        frontier = nxt
    if b not in prev or prev[b] is None:
        return None, None
    toks, cur = [], b
    while cur != a:
        u, rel, dirn = prev[cur]
        toks.append((dirn, rel))
        cur = u
    toks.reverse()
    return tuple(toks), len(toks)

def fingerprints(g, variant):
    scales = {"D0": [("s0", d0(g))], "D1": [("s1", d1(g))],
              "MULTI": [("s0", d0(g)), ("s1", d1(g))]}[variant]
    fps = []
    landmarks = [v for v in range(g.n) if g.adj[v]]
    for (tag, desc) in scales:
        for a in landmarks:
            for b in landmarks:
                if a == b:
                    continue
                sig, dist = pathsig(g, a, b)
                if sig is None:
                    continue
                key = h64(tag, desc[a], desc[b], sig, dist)
                fps.append((key, a, b))
    return fps

# --------------------------------------------------------------------- corpus
def battery():
    roles = ["entity","process","state","outcome","quantity","condition","quantity","quantity"]
    edges = [(0,1,"causes"),(1,2,"causes"),(2,3,"causes"),
             (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),(7,2,"increases")]
    return G("battery", roles, edges)

def named_graphs():
    b = battery()
    gs = [b]
    # cross-domain analog, clean: identical structure (structural channel sees no vocab)
    gs.append(G("org_clean", b.roles, b.edges))
    # realistic analog: D irrelevant branch + E missing edge + I mislabel
    noisy_edges = [(0,1,"causes"),(1,2,"increases"),(2,3,"causes"),      # I: causes->increases
                   (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),
                   (3,8,"causes")]                                        # D: extra branch
    # E: edge (7,2) deleted; node 7 remains isolated
    gs.append(G("org_noisy", b.roles + ["state"], noisy_edges))
    # bare-chain distractors (H's colliding family)
    gs.append(G("marriage_chain", ["entity","process","state","outcome"],
                [(0,1,"causes"),(1,2,"causes"),(2,3,"causes")]))
    gs.append(G("techdebt_chain", ["entity","process","state","outcome","quantity"],
                [(0,1,"causes"),(1,2,"causes"),(2,3,"causes"),(3,4,"causes")]))
    gs.append(G("lake_chain", ["entity","process","state","outcome"],
                [(0,1,"increases"),(1,2,"causes"),(2,3,"causes")]))
    # hard negatives
    gs.append(G("rewired_star", b.roles,
                [(3,0,"causes"),(3,1,"causes"),(3,2,"causes"),(3,4,"causes"),
                 (3,5,"causes"),(3,6,"causes"),(3,7,"causes")]))
    gs.append(G("reversed", b.roles,
                [(1,0,"causes"),(2,1,"causes"),(3,2,"causes"),
                 (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),(7,2,"increases")]))
    gs.append(G("prevents_flip", b.roles,
                [(0,1,"causes"),(1,2,"prevents"),(2,3,"causes"),
                 (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),(7,2,"increases")]))
    # convergence family (fortress/tumor): different motif, mutual analogs
    conv = lambda nm: G(nm, ["agent","agent","agent","agent","process","outcome"],
                        [(0,4,"enables"),(1,4,"enables"),(2,4,"enables"),(3,4,"enables"),
                         (4,5,"causes")])
    gs.append(conv("fortress")); gs.append(conv("tumor"))
    return gs

def filler(rng, world):
    if world == "Z" and rng.random() < 0.8:
        L = rng.randint(3, 5)
        roles = ["entity"] + ["process"]*(L-2) + ["outcome"]
        roles = roles[:L]; roles[min(L-2, L-1)] = "state"
        return G("f", roles, [(i, i+1, "causes") for i in range(L-1)])
    n = rng.randint(6, 12)
    roles = [rng.choice(ROLES) for _ in range(n)]
    edges = [(rng.randint(0, i-1), i, rng.choice(RELS)) for i in range(1, n)]
    for _ in range(max(0, int(n*1.2) - (n-1))):
        u, v = rng.randint(0, n-1), rng.randint(0, n-1)
        if u != v:
            edges.append((u, v, rng.choice(RELS)))
    return G("f", roles, edges)

# ---------------------------------------------------------------- index/query
def build(corpus, variant, max_df_frac=0.005):
    idx, df = defaultdict(list), Counter()
    for tid, g in enumerate(corpus):
        seen = set()
        for (key, a, b) in fingerprints(g, variant):
            idx[key].append((tid, a, b))
            if key not in seen:
                df[key] += 1
                seen.add(key)
    N = len(corpus)
    cutoff = max(5, max_df_frac * N)
    dead = {k for k in df if df[k] > cutoff}
    idf = {k: math.log((N + 1) / (df[k] + 1)) for k in df}
    return idx, idf, dead

def query(g, idx, idf, dead, variant, topk=20):
    qfps = fingerprints(g, variant)
    support = defaultdict(lambda: defaultdict(float))   # tid -> (qn,cn) -> w
    contrib = defaultdict(list)                         # tid -> (w, qa,qb, ca,cb)
    usable, touched = 0.0, 0
    seen_keys = set()
    for (key, qa, qb) in qfps:
        if key in dead or key not in idf:
            continue
        w = idf[key]
        if key not in seen_keys:
            usable += w * sum(1 for (k2, _, _) in qfps if k2 == key)
        seen_keys.add(key)
        posts = idx[key]
        touched += len(posts)
        for (tid, ca, cb) in posts:
            support[tid][(qa, ca)] += w
            support[tid][(qb, cb)] += w
            contrib[tid].append((w, qa, qb, ca, cb))
    usable = sum(idf[k] for (k, _, _) in qfps if k in idf and k not in dead)
    scores = {}
    for tid, sup in support.items():
        pairs = sorted(sup.items(), key=lambda kv: -kv[1])
        pi, used_q, used_c = {}, set(), set()
        for ((qn, cn), w) in pairs:
            if qn in used_q or cn in used_c:
                continue
            pi[qn] = cn; used_q.add(qn); used_c.add(cn)
        coherent = sum(w for (w, qa, qb, ca, cb) in contrib[tid]
                       if pi.get(qa) == ca and pi.get(qb) == cb)
        scores[tid] = coherent / usable if usable > 0 else 0.0
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:topk]
    return ranked, touched

# ------------------------------------------------------------------ execution
def run_world(world, N, variant, seed=20260831):
    rng = random.Random(seed)
    named = named_graphs()
    corpus = named + [filler(rng, world) for _ in range(N - len(named))]
    name_of = {i: g.name for i, g in enumerate(named)}
    t0 = time.time()
    idx, idf, dead = build(corpus, variant)
    tb = time.time() - t0
    t0 = time.time()
    ranked, touched = query(corpus[0], idx, idf, dead, variant)   # query = battery
    tq = time.time() - t0
    ranks = {}
    for pos, (tid, sc) in enumerate(ranked, 1):
        nm = name_of.get(tid, None)
        if nm:
            ranks[nm] = (pos, round(sc, 4))
    chain_names = ["marriage_chain", "techdebt_chain", "lake_chain"]
    org = ranks.get("org_noisy", (999, 0.0))
    worst_chain = min((ranks.get(c, (999, 0.0))[0] for c in chain_names), default=999)
    kill_pass = org[0] < worst_chain and org[0] <= 20
    # fortress/tumor cross-check
    fr, _ = query(corpus[9], idx, idf, dead, variant, topk=10)    # fortress
    fr_names = [name_of.get(t) for t, _ in fr]
    return dict(world=world, N=N, variant=variant, ranks=ranks,
                org_rank=org[0], worst_chain_rank=worst_chain, kill_pass=kill_pass,
                touched=touched, build_s=round(tb, 1), query_ms=round(tq*1000, 1),
                postings=sum(len(v) for v in idx.values()),
                dead_keys=len(dead), live_keys=len(idf) - len(dead),
                tumor_found=("tumor" in fr_names), battery_in_fortress_top=("battery" in fr_names))

def survival_table(variant):
    """B1-style key-set Jaccard of battery vs each named transform (no corpus)."""
    named = named_graphs()
    base = {k for (k, _, _) in fingerprints(named[0], variant)}
    out = {}
    for g in named[1:]:
        ks = {k for (k, _, _) in fingerprints(g, variant)}
        out[g.name] = round(len(base & ks) / len(base | ks), 3) if base | ks else 0.0
    return out

if __name__ == "__main__":
    print("=" * 90)
    print("SURVIVAL (key-set Jaccard vs battery, no corpus, per variant)")
    print("=" * 90)
    for variant in ("D0", "D1", "MULTI"):
        print(f"{variant:6s}", {k: v for k, v in survival_table(variant).items()})
    print()
    header = f"{'world':6s} {'N':>6s} {'var':6s} {'org_rank':>8s} {'chain_best':>10s} {'KILL':>6s} {'touched':>8s} {'postings':>9s} {'dead':>6s} {'q_ms':>7s}"
    for world in ("R", "Z"):
        print("=" * 90)
        print(f"WORLD {world}  ({'rich random fillers' if world=='R' else '80% bare causal chains (H-world)'})")
        print("=" * 90)
        print(header)
        for N in (1000, 10000):
            for variant in ("D0", "D1", "MULTI"):
                r = run_world(world, N, variant)
                print(f"{world:6s} {N:6d} {variant:6s} {r['org_rank']:8d} {r['worst_chain_rank']:10d} "
                      f"{'PASS' if r['kill_pass'] else 'FAIL':>6s} {r['touched']:8d} {r['postings']:9d} "
                      f"{r['dead_keys']:6d} {r['query_ms']:7.1f}")
        # detail at N=10000 MULTI
        r = run_world(world, 10000, "MULTI")
        print(f"\n  detail (N=10000, MULTI): named ranks in top-20: {r['ranks']}")
        print(f"  fortress query: tumor retrieved={r['tumor_found']}, battery contaminates={r['battery_in_fortress_top']}")
        print()
