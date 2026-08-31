"""
R0-C-REVIEW2 bake-off: shared-testbed comparison of C1 / C2 / C3 verifiers.

Run:  /tmp/resonance-c-review/bin/python research/experiments/R0_C_REVIEW2_bakeoff.py
      (or any python3 with numpy + scipy)

Deps: numpy, scipy. No POT, no pygmtools. Each solver is implemented here so
      the comparison is a method comparison, not a library comparison.

Question under test
-------------------
C1, C2, and C3 independently recommended the same pipeline shape
(soft proposal -> discrete injective mapping -> typed-edge rescore) but
disagreed on the proposal generator:

    C1  typed Lawler QAP / RRWM-style association-graph walk
    C2  (partial) FGW with one structural matrix
    C3  multi-relational FGW (one adjacency per relation type + transpose)

This experiment holds the discrete scorer fixed and asks which proposal
generator actually produces the mapping Resonance needs.

Testbed
-------
C3's graphs (cited, not re-authored) plus three C1-required hard negatives:
causal reversal, relation-type swap, and a granularity split. Every pair is
scored over 12 random node relabelings.

This is a proposal-generator bake-off, not a reproduction of C3's published
table (though the multi-rel FGW path should be close, as the solver is the
same Peyre/Vayer conditional-gradient construction C3 used).
"""
from __future__ import annotations

import time
import numpy as np
from scipy.optimize import linear_sum_assignment

np.seterr(all="ignore")

RELS = ["causes", "increases", "prevents"]
DUMMY = "<none>"
REPEATS = 12
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


class G:
    def __init__(self, name, nodes, edges):
        self.name, self.nodes, self.edges = name, list(nodes), list(edges)
        self.n = len(nodes)
        self.C = {}
        for r in RELS:
            A = np.zeros((self.n, self.n))
            for (u, v, rr) in edges:
                if rr == r:
                    A[u, v] = 1.0
            self.C[r] = A
            self.C[r + "^T"] = A.T

    def shortest_undirected(self):
        """C2's simpler symmetrized baseline: hop distance, cap at n."""
        n = self.n
        D = np.full((n, n), float(n))
        np.fill_diagonal(D, 0.0)
        for (u, v, _r) in self.edges:
            D[u, v] = min(D[u, v], 1.0)
            D[v, u] = min(D[v, u], 1.0)
        for k in range(n):
            D = np.minimum(D, D[:, k : k + 1] + D[k : k + 1, :])
        return D


TYPES = RELS + [r + "^T" for r in RELS]


def permute(g, rng):
    perm = rng.permutation(g.n)
    inv = np.argsort(perm)
    nodes = [g.nodes[perm[i]] for i in range(g.n)]
    edges = [(int(inv[u]), int(inv[v]), r) for (u, v, r) in g.edges]
    return G(g.name, nodes, edges)


def pad(g, N):
    if g.n >= N:
        return g
    return G(g.name, g.nodes + [DUMMY] * (N - g.n), g.edges)


def _tensor(C1, C2, pi):
    p, q = pi.sum(1), pi.sum(0)
    return (C1 ** 2) @ p[:, None] @ np.ones((1, C2.shape[0])) \
        + np.ones((C1.shape[0], 1)) @ q[None, :] @ (C2 ** 2).T \
        - 2 * C1 @ pi @ C2.T


def fgw(g1, g2, alpha, mode="multirel", iters=200, tol=1e-12):
    """Vayer/Peyre fused GW, conditional gradient. mode=multirel|path."""
    N = max(g1.n, g2.n)
    g1, g2 = pad(g1, N), pad(g2, N)
    n, m = g1.n, g2.n
    M = np.array([[1.0 - sim(a, b) for b in g2.nodes] for a in g1.nodes])
    if mode == "multirel":
        mats = [(g1.C[t], g2.C[t]) for t in TYPES]
    elif mode == "path":
        mats = [(g1.shortest_undirected(), g2.shortest_undirected())]
    else:
        raise ValueError(mode)
    pi = np.ones((n, m)) / (n * m)

    def energy(pi):
        quad = sum((_tensor(C1, C2, pi) * pi).sum() for C1, C2 in mats)
        return (1 - alpha) * (M * pi).sum() + alpha * quad

    e_prev = energy(pi)
    for _ in range(iters):
        grad = (1 - alpha) * M + alpha * 2 * sum(
            _tensor(C1, C2, pi) for C1, C2 in mats)
        ri, ci = linear_sum_assignment(grad)
        direction = np.zeros((n, m))
        direction[ri, ci] = 1.0 / N
        best, best_e = pi, e_prev
        for gamma in np.linspace(0.02, 1.0, 25):
            cand = (1 - gamma) * pi + gamma * direction
            ec = energy(cand)
            if ec < best_e:
                best, best_e = cand, ec
        if abs(e_prev - best_e) < tol:
            break
        pi, e_prev = best, best_e
    return pi


def rrwm_coupling(g1, g2, top_d=None, wn=1.0, we=5.0, iters=40):
    """
    C1-style sparse Lawler QAP solved by association-graph random walks
    with Sinkhorn 1-1 reweighting (RRWM-adjacent, not bit-exact pygmtools).

    top_d=None keeps all pairs (structure can rescue cross-domain).
    top_d=k keeps each node's k nearest semantic matches (C1 failure mode 2).
    """
    n, m = g1.n, g2.n
    U = np.array([[sim(a, b) for b in g2.nodes] for a in g1.nodes])
    allowed = np.ones((n, m), dtype=bool)
    if top_d is not None:
        allowed[:, :] = False
        for i in range(n):
            order = np.argsort(-U[i])
            allowed[i, order[: min(top_d, m)]] = True
        # isolated columns stay unmatched; that is the pruning failure mode

    pairs = [(i, j) for i in range(n) for j in range(m) if allowed[i, j]]
    if not pairs:
        return np.zeros((n, m))
    p = len(pairs)
    index = {pair: k for k, pair in enumerate(pairs)}
    K = np.zeros((p, p))
    for a, (i, j) in enumerate(pairs):
        K[a, a] = wn * max(U[i, j], 0.0)
    # C1 pairwise term: directed typed edges with matching type.
    # Index by edges, not by candidate-pair Cartesian product.
    for (i, k, r) in g1.edges:
        for (j, l, r2) in g2.edges:
            if r != r2:
                continue
            a = index.get((i, j))
            b = index.get((k, l))
            if a is None or b is None or a == b:
                continue
            if i == k or j == l:
                continue
            K[a, b] += we
            K[b, a] += we
    # tiny self-loop so a zero-row does not kill the walk
    K = K + 1e-6 * np.eye(p)
    x = np.ones(p) / p
    for t in range(iters):
        x = np.maximum(K @ x, 0.0)
        s = x.sum()
        x = x / s if s > 0 else np.ones(p) / p
        # Cho-style 1-1 reweighting: Sinkhorn on the assignment matrix,
        # every few steps so the walk can still mix.
        if t % 4 == 3:
            X = np.zeros((n, m))
            for a, (i, j) in enumerate(pairs):
                X[i, j] = x[a]
            for _s in range(5):
                rs = X.sum(axis=1, keepdims=True)
                rs[rs == 0] = 1.0
                X = X / rs
                cs = X.sum(axis=0, keepdims=True)
                cs[cs == 0] = 1.0
                X = X / cs
            x = np.array([X[i, j] for (i, j) in pairs])
            s = x.sum()
            x = x / s if s > 0 else np.ones(p) / p
    # Return the soft assignment. Shared Hungarian in score() is the
    # discrete step; do not dummy-pad here (a previous unmatched-cost
    # calibration emptied every mapping and would have falsely "falsified" C1).
    X = np.zeros((n, m))
    for a, (i, j) in enumerate(pairs):
        X[i, j] = x[a] + 0.05 * U[i, j]
    return X


def semantic_coupling(g1, g2):
    M = np.array([[sim(a, b) for b in g2.nodes] for a in g1.nodes])
    return M  # score() Hungarian-discretizes -M equivalently via -pi


def score(g1, g2, pi):
    if pi.size == 0 or pi.shape != (g1.n, g2.n):
        # FGW pads; slice back if needed
        n1, n2 = g1.n, g2.n
        if pi.shape[0] >= n1 and pi.shape[1] >= n2:
            pi = pi[:n1, :n2]
        else:
            return dict(struct=0.0, sem=0.0, cover=0.0, kappa=0.0, map=[])
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
    s_struct = preserved / max(len(g1.edges), len(g2.edges), 1)
    s_sem = float(np.mean([sim(g1.nodes[i], g2.nodes[j]) for i, j in keep]))
    cover = len(keep) / min(n1, n2)
    adj = {i: set() for i, _ in keep}
    for (u, v, r) in g1.edges:
        if u in phi and v in phi and (phi[u], phi[v], r) in e2:
            adj[u].add(v)
            adj[v].add(u)
    seen, big = set(), 0
    for s in adj:
        if s in seen:
            continue
        stack, comp = [s], 0
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp += 1
            stack.extend(adj[x] - seen)
        big = max(big, comp)
    return dict(struct=s_struct, sem=s_sem, cover=cover,
                kappa=big / len(keep), map=keep)


# --------------------------------------------------------------------------
# graphs: C3 testbed (cited) + C1-required extra negatives
# --------------------------------------------------------------------------
STRUCT = [(0, 1, "causes"), (1, 2, "causes"), (2, 3, "causes"),
          (4, 1, "increases"), (5, 1, "prevents"), (3, 6, "causes"),
          (7, 2, "increases")]

NODES = ["battery", "heat_accum", "degradation", "failure", "load",
         "cooling", "repl_cost", "age"]

BASE = G("battery(base)", NODES, STRUCT)
PARA = G("battery(paraphrase)",
         ["cell", "thermal_buildup", "wear", "breakdown", "demand",
          "heat_sink", "replacement_cost", "service_years"], STRUCT)
ANALOG = G("organization(cross-domain)",
           ["organization", "info_accum", "coord_degradation", "org_failure",
            "workload", "delegation", "restructure_cost", "tenure"], STRUCT)
HARDNEG = G("battery(SAME words, rewired star)",
            NODES,
            [(3, 0, "causes"), (3, 1, "causes"), (3, 2, "causes"),
             (3, 4, "causes"), (3, 5, "causes"), (3, 6, "causes"),
             (3, 7, "causes")])
GEN1 = G("generic short chain",
         ["thing_a", "thing_b", "thing_c", "thing_d",
          "thing_e", "thing_f", "thing_g", "thing_h"],
         [(0, 1, "causes"), (1, 2, "causes")])
GEN2 = G("generic long chain",
         ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"],
         [(i, i + 1, "causes") for i in range(7)])
PARTIAL = G("organization fragment",
            ["organization", "info_accum", "coord_degradation", "org_failure"],
            [(0, 1, "causes"), (1, 2, "causes"), (2, 3, "causes")])
NOISY = G("organization NOISY (D+E+I)",
          ["organization", "info_accum", "coord_degradation", "org_failure",
           "workload", "delegation", "restructure_cost", "tenure", "side_issue"],
          [(0, 1, "causes"), (1, 2, "increases"),
           (4, 1, "increases"), (5, 1, "prevents"), (3, 6, "causes"),
           (7, 2, "increases"), (2, 8, "causes"), (8, 3, "causes")])
REVERSE = G("battery(causal reversal)",
            NODES, [(v, u, r) for (u, v, r) in STRUCT])
SWAP = {"causes": "prevents", "prevents": "causes", "increases": "increases"}
TYPESWAP = G("battery(causes<->prevents)",
             NODES, [(u, v, SWAP[r]) for (u, v, r) in STRUCT])
# granularity: A->B becomes A->X->B on the main chain 0-1-2-3
GRANULAR = G("battery(granularity split)",
             NODES + ["mid_heat", "mid_deg", "mid_fail"],
             [(0, 8, "causes"), (8, 1, "causes"),
              (1, 9, "causes"), (9, 2, "causes"),
              (2, 10, "causes"), (10, 3, "causes"),
              (4, 1, "increases"), (5, 1, "prevents"),
              (3, 6, "causes"), (7, 2, "increases")])

CASES = [
    ("PARAPHRASE           (pos)", PARA),
    ("CROSS-DOMAIN         (pos)", ANALOG),
    ("NOISY cross-dom      (pos)", NOISY),
    ("PARTIAL frag         (pos)", PARTIAL),
    ("SAME WORDS/REWIRED   (neg)", HARDNEG),
    ("GENERIC short        (neg)", GEN1),
    ("GENERIC long         (neg)", GEN2),
    ("CAUSAL REVERSAL      (neg)", REVERSE),
    ("TYPE SWAP            (neg)", TYPESWAP),
    ("GRANULARITY split    (ctrl)", GRANULAR),
]

# proposal generators. FGW methods close over alpha via wrappers below.
METHODS = [
    ("SEM-Hungarian", lambda a, b: semantic_coupling(a, b)),
    ("C1-RRWM-all", lambda a, b: rrwm_coupling(a, b, top_d=None)),
    ("C1-RRWM-sem3", lambda a, b: rrwm_coupling(a, b, top_d=3)),
    ("C2-FGW-path-a07", lambda a, b: fgw(a, b, 0.7, mode="path")),
    ("C3-FGW-multi-a00", lambda a, b: fgw(a, b, 0.0, mode="multirel")),
    ("C3-FGW-multi-a07", lambda a, b: fgw(a, b, 0.7, mode="multirel")),
]


def correspondence_acc(g, gp, mapping, base_n):
    if g.n != base_n:
        return float("nan")
    pos = {n: i for i, n in enumerate(gp.nodes)}
    try:
        truth = {i: pos[g.nodes[i]] for i in range(g.n)}
    except KeyError:
        return float("nan")
    if not mapping:
        return 0.0
    return sum(1 for i, j in mapping if truth.get(i) == j) / g.n


def evaluate(method_name, proposer, rng):
    rows = {}
    for label, g in CASES:
        st, se, cv, kp, acc = [], [], [], [], []
        for _ in range(REPEATS):
            gp = permute(g, rng)
            pi = proposer(BASE, gp)
            s_ = score(BASE, gp, pi)
            st.append(s_["struct"])
            se.append(s_["sem"])
            cv.append(s_["cover"])
            kp.append(s_["kappa"])
            acc.append(correspondence_acc(g, gp, s_["map"], BASE.n))
        def m(v):
            finite = [x for x in v if x == x]
            return float(np.mean(finite)) if finite else float("nan")
        rows[label] = dict(
            struct=m(st), struct_lo=min(st), struct_hi=max(st),
            sem=m(se), cover=m(cv), kappa=m(kp), acc=m(acc),
        )
    return rows


def print_table(name, rows):
    print(f"\n=== {name} ===")
    print(f"{'case':28s} {'S_struct':>16s} {'S_sem':>7s} {'cover':>6s} "
          f"{'kappa':>6s} {'corr.acc':>9s}")
    for label, _g in CASES:
        r = rows[label]
        print(f"{label:28s} {r['struct']:7.3f} "
              f"[{r['struct_lo']:.2f},{r['struct_hi']:.2f}] "
              f"{r['sem']:7.3f} {r['cover']:6.2f} {r['kappa']:6.2f} "
              f"{r['acc']:9.3f}")


def gate(rows):
    """Combined kill rules drawn from C1/C2/C3's own falsification language."""
    cd = rows["CROSS-DOMAIN         (pos)"]
    noisy = rows["NOISY cross-dom      (pos)"]
    hn = rows["SAME WORDS/REWIRED   (neg)"]
    gen = rows["GENERIC long         (neg)"]
    rev = rows["CAUSAL REVERSAL      (neg)"]
    swap = rows["TYPE SWAP            (neg)"]
    para = rows["PARAPHRASE           (pos)"]
    checks = [
        ("F1 paraphrase struct>=0.8", para["struct"] >= 0.8),
        ("F2 cross-domain struct>=0.8", cd["struct"] >= 0.8),
        ("F3 cross-domain acc>=0.8", cd["acc"] >= 0.8),
        ("F4 cd-rewired gap>=0.5", cd["struct"] - hn["struct"] >= 0.5),
        ("F5 noisy > generic-long", noisy["struct"] > gen["struct"] + 1e-9),
        ("F6 reversal struct < cd-0.3", rev["struct"] <= cd["struct"] - 0.3),
        ("F7 typeswap struct < cd-0.3", swap["struct"] <= cd["struct"] - 0.3),
        ("F8 cd sem < 0.3 (not topical)", cd["sem"] < 0.3),
    ]
    return checks


def rand_graph(n, rng, deg=2.5):
    e = set()
    for _ in range(int(n * deg)):
        u, v = int(rng.integers(n)), int(rng.integers(n))
        if u != v:
            e.add((u, v, RELS[int(rng.integers(len(RELS)))]))
    return G(f"rand{n}", [f"c{i}" for i in range(n)], sorted(e))


if __name__ == "__main__":
    print("R0-C-REVIEW2 bake-off")
    print("numpy", np.__version__)
    import scipy
    print("scipy", scipy.__version__)
    print(f"repeats={REPEATS}  (random node relabelings per case)")

    all_rows = {}
    for name, fn in METHODS:
        rng = np.random.default_rng(20260831)
        t0 = time.time()
        rows = evaluate(name, fn, rng)
        dt = time.time() - t0
        all_rows[name] = rows
        print_table(f"{name}  ({dt:.2f}s)", rows)

    print("\n" + "=" * 78)
    print("KILL RULES  (method x check). PASS = the proposal generator,")
    print("after shared typed-edge rescoring, satisfies that C1/C2/C3 gate.")
    print("=" * 78)
    check_names = None
    for name, _fn in METHODS:
        checks = gate(all_rows[name])
        if check_names is None:
            check_names = [c[0] for c in checks]
        passed = sum(1 for _n, ok in checks if ok)
        bits = " ".join("P" if ok else "F" for _n, ok in checks)
        print(f"{name:22s} {passed}/{len(checks)}  {bits}")
    print("\ncheck order:")
    for i, n in enumerate(check_names, 1):
        print(f"  {i}. {n}")

    print("\n" + "=" * 78)
    print("HEADLINE MARGINS  (mean S_struct)")
    print("=" * 78)
    hdr = f"{'method':22s} {'cd':>7s} {'noisy':>7s} {'rewire':>7s} " \
          f"{'genL':>7s} {'rev':>7s} {'swap':>7s} {'gran':>7s}"
    print(hdr)
    for name, _fn in METHODS:
        r = all_rows[name]
        print(f"{name:22s} "
              f"{r['CROSS-DOMAIN         (pos)']['struct']:7.3f} "
              f"{r['NOISY cross-dom      (pos)']['struct']:7.3f} "
              f"{r['SAME WORDS/REWIRED   (neg)']['struct']:7.3f} "
              f"{r['GENERIC long         (neg)']['struct']:7.3f} "
              f"{r['CAUSAL REVERSAL      (neg)']['struct']:7.3f} "
              f"{r['TYPE SWAP            (neg)']['struct']:7.3f} "
              f"{r['GRANULARITY split    (ctrl)']['struct']:7.3f}")

    print("\n" + "=" * 78)
    print("RUNTIME  (one 50x50 pair, single core, this implementation)")
    print("=" * 78)
    rr = np.random.default_rng(3)
    a50, b50 = rand_graph(50, rr), rand_graph(50, rr)
    runtime_methods = [
        ("SEM-Hungarian", lambda: semantic_coupling(a50, b50)),
        ("C1-RRWM-all", lambda: rrwm_coupling(a50, b50, top_d=None, iters=20)),
        ("C2-FGW-path-a07", lambda: fgw(a50, b50, 0.7, mode="path", iters=50)),
        ("C3-FGW-multi-a07", lambda: fgw(a50, b50, 0.7, mode="multirel", iters=50)),
    ]
    for name, fn in runtime_methods:
        t0 = time.time()
        fn()
        dt = time.time() - t0
        print(f"  {name:22s} {dt*1000:8.1f} ms/pair   top-20: {dt*20:6.2f}s")
