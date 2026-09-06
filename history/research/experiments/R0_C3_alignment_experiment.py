"""
R0-C3 falsification experiment: multi-relational Fused Gromov-Wasserstein as a
Thought-Graph verifier.

Run:  python3 R0_C3_alignment_experiment.py
Deps: numpy, scipy  (no POT required -- the FGW conditional-gradient solver is
      implemented here directly so the experiment is reproducible on a bare box)

Question under test
-------------------
Can a verifier separate the two cases the Resonance brief calls central?

    different words, same structure   -> TRUE analogy, must score HIGH
    same words, different structure   -> FALSE positive, must score LOW

and does it do so WITHOUT collapsing every generic causal chain onto every
other one (structural collapse) when the structure term dominates?

Falsification criteria are printed at the end.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

# numpy 2.x on macOS/Accelerate raises spurious divide-by-zero/overflow flags
# from matmul on all-finite input; verified the results are finite and correct.
np.seterr(all='ignore')

RELS = ["causes", "increases", "prevents"]

# --------------------------------------------------------------------------
# semantic similarity ORACLE (stipulated, not learned -- see report caveat)
# --------------------------------------------------------------------------
SYNONYMS = [
    {"battery", "cell"}, {"heat_accum", "thermal_buildup"},
    {"degradation", "wear"}, {"failure", "breakdown"},
    {"load", "demand"}, {"cooling", "heat_sink"},
    {"repl_cost", "replacement_cost"}, {"age", "service_years"},
]

def sim(a, b):
    if a == DUMMY or b == DUMMY:
        return 0.0
    if a == b:
        return 1.0
    for s in SYNONYMS:
        if a in s and b in s:
            return 0.85
    return 0.05

DUMMY = "<none>"

class G:
    def __init__(self, name, nodes, edges):
        self.name, self.nodes, self.edges = name, list(nodes), list(edges)
        self.n = len(nodes)
        # one adjacency matrix per relation type, plus its transpose as a
        # distinct type so that EDGE DIRECTION is part of the structure term
        self.C = {}
        for r in RELS:
            A = np.zeros((self.n, self.n))
            for (u, v, rr) in edges:
                if rr == r:
                    A[u, v] = 1.0
            self.C[r] = A
            self.C[r + "^T"] = A.T

TYPES = RELS + [r + "^T" for r in RELS]

def permute(g, rng):
    """Relabel node order. Without this the identity permutation is trivially
    findable and every score is an artifact of construction order."""
    perm = rng.permutation(g.n)
    inv = np.argsort(perm)
    nodes = [g.nodes[perm[i]] for i in range(g.n)]
    edges = [(int(inv[u]), int(inv[v]), r) for (u, v, r) in g.edges]
    return G(g.name, nodes, edges)

def pad(g, N):
    """Pad with edge-less DUMMY nodes so both graphs share size N. A match to a
    DUMMY node IS the unmatched-node case (the GED epsilon-node convention)."""
    if g.n >= N:
        return g
    return G(g.name, g.nodes + [DUMMY] * (N - g.n), g.edges)

# --------------------------------------------------------------------------
# multi-relational FGW  (Peyre et al. 2016 square-loss decomposition,
# Vayer et al. 2019 fused term, conditional-gradient / Frank-Wolfe solver)
#   E(pi) = (1-a) * <M, pi>  +  a * sum_r sum_ijkl |C1^r_ik - C2^r_jl|^2 pi_ij pi_kl
# --------------------------------------------------------------------------
def _tensor(C1, C2, pi):
    """<L(C1,C2) (x) pi> via f1(a)=a^2, f2(b)=b^2, h1(a)=a, h2(b)=2b."""
    p, q = pi.sum(1), pi.sum(0)
    return (C1 ** 2) @ p[:, None] @ np.ones((1, C2.shape[0])) \
         + np.ones((C1.shape[0], 1)) @ q[None, :] @ (C2 ** 2).T \
         - 2 * C1 @ pi @ C2.T

def fgw(g1, g2, alpha, iters=200, tol=1e-12, seed_pi=None):
    N = max(g1.n, g2.n)
    g1, g2 = pad(g1, N), pad(g2, N)
    n, m = g1.n, g2.n
    M = np.array([[1.0 - sim(a, b) for b in g2.nodes] for a in g1.nodes])
    pi = seed_pi if seed_pi is not None else np.ones((n, m)) / (n * m)
    # uniform marginals 1/N each -> the Birkhoff polytope scaled by 1/N

    def energy(pi):
        quad = sum((_tensor(g1.C[t], g2.C[t], pi) * pi).sum() for t in TYPES)
        return (1 - alpha) * (M * pi).sum() + alpha * quad

    e_prev = energy(pi)
    for _ in range(iters):
        grad = (1 - alpha) * M + alpha * 2 * sum(
            _tensor(g1.C[t], g2.C[t], pi) for t in TYPES)
        # LP oracle over the partial-transport polytope: rectangular Hungarian
        # gives an injective partial assignment -> unmatched nodes are allowed
        ri, ci = linear_sum_assignment(grad)
        direction = np.zeros((n, m))
        direction[ri, ci] = 1.0 / N
        best, best_e = pi, e_prev
        for gamma in np.linspace(0.02, 1.0, 25):      # line search
            cand = (1 - gamma) * pi + gamma * direction
            ec = energy(cand)
            if ec < best_e:
                best, best_e = cand, ec
        if abs(e_prev - best_e) < tol:
            break
        pi, e_prev = best, best_e
    return pi

# --------------------------------------------------------------------------
# scoring -- reported as a VECTOR, deliberately never blended into one number
# --------------------------------------------------------------------------
def score(g1, g2, pi):
    ri, ci = linear_sum_assignment(-pi)
    n1, n2 = g1.n, g2.n
    keep = [(i, j) for i, j in zip(ri, ci)
            if pi[i, j] > 1e-9 and i < n1 and j < n2
            and g1.nodes[i] != DUMMY and g2.nodes[j] != DUMMY]
    if not keep:
        return dict(struct=0.0, sem=0.0, cover=0.0, kappa=0.0, map=[])
    phi = dict(keep)
    e2 = {(u, v, r) for (u, v, r) in g2.edges}
    preserved = sum(1 for (u, v, r) in g1.edges
                    if u in phi and v in phi and (phi[u], phi[v], r) in e2)
    s_struct = preserved / max(len(g1.edges), len(g2.edges))
    s_sem = float(np.mean([sim(g1.nodes[i], g2.nodes[j]) for i, j in keep]))
    cover = len(keep) / min(n1, n2)
    # systematicity: largest connected component of the matched subgraph
    adj = {i: set() for i, _ in keep}
    for (u, v, r) in g1.edges:
        if u in phi and v in phi and (phi[u], phi[v], r) in e2:
            adj[u].add(v); adj[v].add(u)
    seen, big = set(), 0
    for s in adj:
        if s in seen: continue
        stack, comp = [s], 0
        while stack:
            x = stack.pop()
            if x in seen: continue
            seen.add(x); comp += 1
            stack.extend(adj[x] - seen)
        big = max(big, comp)
    return dict(struct=s_struct, sem=s_sem, cover=cover,
                kappa=big / len(keep), map=keep)

# --------------------------------------------------------------------------
# test graphs
# --------------------------------------------------------------------------
STRUCT = [(0,1,"causes"),(1,2,"causes"),(2,3,"causes"),
          (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),(7,2,"increases")]

BASE = G("battery(base)",
    ["battery","heat_accum","degradation","failure","load","cooling","repl_cost","age"],
    STRUCT)

PARA = G("battery(paraphrase)",
    ["cell","thermal_buildup","wear","breakdown","demand","heat_sink","replacement_cost","service_years"],
    STRUCT)

ANALOG = G("organization(cross-domain, SAME structure)",
    ["organization","info_accum","coord_degradation","org_failure","workload","delegation","restructure_cost","tenure"],
    STRUCT)

HARDNEG = G("battery(SAME words, rewired)",
    BASE.nodes,
    [(3,0,"causes"),(3,1,"causes"),(3,2,"causes"),(3,4,"causes"),
     (3,5,"causes"),(3,6,"causes"),(3,7,"causes")])          # star, not chain

GEN1 = G("generic short chain + isolates",
    ["thing_a","thing_b","thing_c","thing_d","thing_e","thing_f","thing_g","thing_h"],
    [(0,1,"causes"),(1,2,"causes")])

GEN2 = G("generic long chain",
    ["x0","x1","x2","x3","x4","x5","x6","x7"],
    [(i,i+1,"causes") for i in range(7)])

PARTIAL = G("organization fragment (4 nodes)",
    ["organization","info_accum","coord_degradation","org_failure"],
    [(0,1,"causes"),(1,2,"causes"),(2,3,"causes")])

# cross-domain analogue degraded by invariances D (inserted branch),
# E (deleted edge) and I (one mislabeled relation) -- the realistic case
NOISY = G("organization NOISY (D+E+I)",
    ["organization","info_accum","coord_degradation","org_failure","workload",
     "delegation","restructure_cost","tenure","side_issue"],
    [(0,1,"causes"),(1,2,"increases"),          # I: causes -> increases
     (4,1,"increases"),(5,1,"prevents"),(3,6,"causes"),(7,2,"increases"),
     (2,8,"causes"),(8,3,"causes")])            # E: 2->3 removed, D: via side_issue

CASES = [("PARAPHRASE      (pos)", PARA),
         ("CROSS-DOMAIN    (pos)", ANALOG),
         ("NOISY cross-dom (pos)", NOISY),
         ("PARTIAL frag    (pos)", PARTIAL),
         ("SAME WORDS/REWIRED (neg)", HARDNEG),
         ("GENERIC short   (neg)", GEN1),
         ("GENERIC long    (neg)", GEN2)]

REPEATS = 12   # random node relabelings per case; guards against order artifacts

def run(alpha, rng):
    print(f"\n=== alpha = {alpha:.2f}  ({'pure structure' if alpha==1.0 else 'pure semantics' if alpha==0.0 else 'fused'}) ===")
    print(f"{'case':26s} {'S_struct':>16s} {'S_sem':>7s} {'cover':>6s} {'kappa':>6s} {'corr.acc':>9s}")
    out = {}
    for label, g in CASES:
        st, se, cv, kp, acc = [], [], [], [], []
        for _ in range(REPEATS):
            gp = permute(g, rng)
            pos = {n: i for i, n in enumerate(gp.nodes)}
            s_ = score(BASE, gp, fgw(BASE, gp, alpha))
            st.append(s_['struct']); se.append(s_['sem'])
            cv.append(s_['cover']); kp.append(s_['kappa'])
            # ground truth: BASE index i corresponds to the node that sat at i
            # before permutation, so accuracy is measurable for equal-size cases
            if g.n == BASE.n:
                truth = {i: pos[g.nodes[i]] for i in range(g.n)}
                acc.append(sum(1 for i, j in s_['map'] if truth.get(i) == j) / g.n)
        m = lambda v: float(np.mean(v)) if v else float('nan')
        lo, hi = (min(st), max(st))
        out[label] = dict(struct=m(st), sem=m(se), cover=m(cv), kappa=m(kp), acc=m(acc))
        print(f"{label:26s} {m(st):7.3f} [{lo:.2f},{hi:.2f}] {m(se):7.3f} {m(cv):6.2f} {m(kp):6.2f} {m(acc):9.3f}")
    return out

if __name__ == "__main__":
    rng = np.random.default_rng(20260831)
    res = {a: run(a, np.random.default_rng(20260831)) for a in (0.0, 0.3, 0.5, 0.7, 0.9, 1.0)}

    print("\n" + "=" * 78)
    print("FALSIFICATION CHECKS  (mean over %d random relabelings)" % REPEATS)
    print("=" * 78)
    print(f"{'alpha':>6s} {'F1 cd>=.8':>10s} {'F2 gap(cd-rewired)>=.5':>24s} {'F3 gap(cd-generic)>=.3':>24s} {'F4 sem<.3':>10s}")
    for a in (0.0, 0.3, 0.5, 0.7, 0.9, 1.0):
        r = res[a]
        cd = r["CROSS-DOMAIN    (pos)"]; hn = r["SAME WORDS/REWIRED (neg)"]
        g2 = r["GENERIC long    (neg)"]
        f1 = cd["struct"] >= 0.8
        f2 = cd["struct"] - hn["struct"] >= 0.5
        f3 = cd["struct"] - g2["struct"] >= 0.3
        f4 = cd["sem"] < 0.3
        P = lambda b: "PASS" if b else "FAIL"
        print(f"{a:6.2f} {P(f1):>10s} {P(f2):>24s} {P(f3):>24s} {P(f4):>10s}")

    # ------------------------------------------------------------------
    # Does seeding help?  R0-B2 (same author -- see report's anchoring
    # disclosure) claimed retrieval should hand the verifier seed node
    # correspondences. FGW is non-convex, so this is testable directly.
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SEEDED vs UNSEEDED  (alpha=0.7, NOISY cross-domain, %d relabelings)" % REPEATS)
    print("=" * 78)
    rng2 = np.random.default_rng(7)
    for nseeds in (0, 1, 2, 3):
        accs, structs = [], []
        for _ in range(REPEATS):
            gp = permute(NOISY, rng2)
            pos = {n: i for i, n in enumerate(gp.nodes)}
            truth = {i: pos[NOISY.nodes[i]] for i in range(BASE.n)}
            N = max(BASE.n, gp.n)
            if nseeds == 0:
                pi0 = None
            else:
                pi0 = np.ones((N, N)) / (N * N)
                # bias the initial coupling toward nseeds TRUE correspondences,
                # exactly what a fingerprint-stage consistency vote would emit
                for i in sorted(truth)[:nseeds]:
                    pi0[i, :] *= 0.1
                    pi0[i, truth[i]] = 1.0 / N
                pi0 /= pi0.sum()
            sc = score(BASE, gp, fgw(BASE, gp, 0.7, seed_pi=pi0))
            hit = sum(1 for i, j in sc['map'] if truth.get(i) == j)
            accs.append(hit / max(1, len(truth))); structs.append(sc['struct'])
        print(f"  seeds={nseeds}:  correspondence acc = {np.mean(accs):.3f} "
              f"(sd {np.std(accs):.3f})   S_struct = {np.mean(structs):.3f} "
              f"(sd {np.std(structs):.3f})")

    # ------------------------------------------------------------------
    # runtime: mission asks for 50x50 nodes and top-20 candidate verification
    # ------------------------------------------------------------------
    import time
    print("\n" + "=" * 78); print("RUNTIME (this pure-numpy CG solver, single core)"); print("=" * 78)
    rr = np.random.default_rng(3)
    def rand_graph(n, deg=2.5):
        e = set()
        for _ in range(int(n * deg)):
            u, v = int(rr.integers(n)), int(rr.integers(n))
            if u != v: e.add((u, v, RELS[int(rr.integers(len(RELS)))]))
        return G(f"rand{n}", [f"c{i}" for i in range(n)], sorted(e))
    for n in (10, 25, 50, 100):
        a, b = rand_graph(n), rand_graph(n)
        t0 = time.time(); fgw(a, b, 0.7); dt = time.time() - t0
        print(f"  {n:3d}x{n:3d} nodes: {dt*1000:8.1f} ms/pair   "
              f"top-20 candidates: {dt*20:6.2f} s")
