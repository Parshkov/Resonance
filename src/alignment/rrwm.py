"""Sparse Lawler-QAP proposal via simplified reweighted random walks.

Gate candidate per ADR-0003 (co-equal with FGW-CG). Association-graph
variables are node pairs (i, j); pairwise affinity rewards preserved typed
directed propositions; unary affinity is the node-affinity matrix. No
semantic top-d pruning of candidate pairs (v0.1 prohibition).

This is a deterministic simplified RRWM (power iteration with personalized
restart and row/column reweighting), not the pygmtools implementation --
recorded as such per ADR-0003's own bake-off caveat.
"""

from __future__ import annotations

from ._view import RELATION_TYPES, GraphView

Matrix = list[list[float]]


def solve_rrwm(
    view_a: GraphView,
    view_b: GraphView,
    affinity: Matrix,
    *,
    iters: int = 40,
    beta: float = 0.2,
    seeds: tuple[tuple[int, int, float], ...] = (),
) -> list[Matrix]:
    n, m = view_a.n, view_b.n
    N = max(n, m)
    # sparse pairwise affinity: ((i,j),(k,l)) whenever edge i->k and j->l share
    # type, assertion and modality; weight = min conf.
    pair_edges: list[tuple[int, int, int, int, float]] = []
    for t in RELATION_TYPES:
        for (i, k, wa, ra) in view_a.channels.get(t, []):
            for (j, l, wb, rb) in view_b.channels.get(t, []):
                if ra.assertion == rb.assertion and ra.modality == rb.modality:
                    pair_edges.append((i, j, k, l, min(wa, wb)))

    def run(x0: Matrix) -> Matrix:
        x = [row[:] for row in x0]
        for _ in range(iters):
            y = [[0.0] * N for _ in range(N)]
            for (i, j, k, l, w) in pair_edges:
                y[i][j] += w * x[k][l]
                y[k][l] += w * x[i][j]
            for i in range(min(n, N)):
                for j in range(min(m, N)):
                    y[i][j] += 0.5 * affinity[i][j] * x[i][j]
            total = sum(sum(row) for row in y)
            if total <= 1e-15:
                return x
            restart = beta / (N * N)
            x = [[(1 - beta) * (y[i][j] / total) + restart for j in range(N)]
                 for i in range(N)]
            # reweighted jump: two rounds of row/column normalisation keeps the
            # walk near the assignment polytope without full Sinkhorn cost.
            for _round in range(2):
                for i in range(N):
                    s = sum(x[i])
                    if s > 0:
                        x[i] = [v / (s * N) for v in x[i]]
                for j in range(N):
                    s = sum(x[i][j] for i in range(N))
                    if s > 0:
                        for i in range(N):
                            x[i][j] /= (s * N)
        return x

    uniform = [[1.0 / (N * N)] * N for _ in range(N)]
    outs = [run(uniform)]
    if seeds:
        seeded = [row[:] for row in uniform]
        for (qi, cj, support) in seeds:
            if 0 <= qi < n and 0 <= cj < m:
                seeded[qi][cj] += support / N
        total = sum(sum(row) for row in seeded)
        seeded = [[v / total for v in row] for row in seeded]
        outs.append(run(seeded))
    return outs
