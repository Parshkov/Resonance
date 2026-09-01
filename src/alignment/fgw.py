"""Multi-relational Fused Gromov-Wasserstein proposal solver (conditional gradient).

ADR-0003 prototype default: one directed 0/1-confidence adjacency channel per
relation type PLUS its transpose as a distinct channel; alpha ~ 0.7. Square
loss; the Peyre et al. (2016) decomposition is applied channel-sparsely, so
cost per iteration is O(sum_t (nnz1_t + nnz2_t) * n) instead of O(n^2 m^2).

Unmatched nodes: epsilon-padding to a common size N = max(n, m); a match to a
padding slot is "unmatched" (declared FGW-family variant per ADR-0003).

Deterministic: fixed initialisations only (uniform + optional seed-biased),
exact quadratic line search, no randomness.
"""

from __future__ import annotations

from ._hungarian import solve as hungarian
from ._view import RELATION_TYPES, GraphView

Matrix = list[list[float]]


def _channels(view: GraphView, N: int) -> list[list[tuple[int, int, float]]]:
    """Per-type sparse channels + transposes, padded to N (padding has no edges)."""
    out: list[list[tuple[int, int, float]]] = []
    for t in RELATION_TYPES:
        fwd = [(i, j, conf) for (i, j, conf, _rel) in view.channels.get(t, [])]
        out.append(fwd)
        out.append([(j, i, conf) for (i, j, conf) in fwd])
    return out


def _sparse_ApiB(A: list[tuple[int, int, float]], pi: Matrix,
                 B: list[tuple[int, int, float]], N: int) -> Matrix:
    """Compute A @ pi @ B^T for sparse 0/1-confidence channels."""
    # tmp = A @ pi : row i of tmp accumulates w * pi[k]
    tmp = [[0.0] * N for _ in range(N)]
    for (i, k, w) in A:
        row_pi = pi[k]
        row_t = tmp[i]
        for j in range(N):
            row_t[j] += w * row_pi[j]
    # out = tmp @ B^T : out[i][j] = sum_l tmp[i][l] * B[j][l]
    out = [[0.0] * N for _ in range(N)]
    for (j, l, w) in B:
        for i in range(N):
            out[i][j] += w * tmp[i][l]
    return out


def _degree_terms(A: list[tuple[int, int, float]], B: list[tuple[int, int, float]],
                  pi: Matrix, N: int) -> tuple[list[float], list[float]]:
    """Row/col constant parts of the square-loss tensor for 0/1-conf channels:
    c1[i] = sum_k A[i,k]^2 * p[k],  c2[j] = sum_l B[j,l]^2 * q[l] with
    p, q the marginals of pi."""
    p = [sum(row) for row in pi]
    q = [0.0] * N
    for row in pi:
        for j in range(N):
            q[j] += row[j]
    c1 = [0.0] * N
    for (i, k, w) in A:
        c1[i] += (w * w) * p[k]
    c2 = [0.0] * N
    for (j, l, w) in B:
        c2[j] += (w * w) * q[l]
    return c1, c2


def _quad_energy_and_grad(chans_a, chans_b, pi: Matrix, N: int) -> tuple[float, Matrix]:
    """Energy sum_t <L_t (x) pi, pi> and gradient 2 * sum_t L_t (x) pi."""
    grad = [[0.0] * N for _ in range(N)]
    energy = 0.0
    for A, B in zip(chans_a, chans_b):
        if not A and not B:
            continue
        cross = _sparse_ApiB(A, pi, B, N)
        c1, c2 = _degree_terms(A, B, pi, N)
        for i in range(N):
            gi = grad[i]
            ci = c1[i]
            row_cross = cross[i]
            row_pi = pi[i]
            for j in range(N):
                t_ij = ci + c2[j] - 2.0 * row_cross[j]
                gi[j] += 2.0 * t_ij
                energy += t_ij * row_pi[j]
    return energy, grad


def _lin_energy(M: Matrix, pi: Matrix, N: int) -> float:
    return sum(M[i][j] * pi[i][j] for i in range(N) for j in range(N))


def _quad_at(chans_a, chans_b, pi: Matrix, N: int) -> float:
    energy = 0.0
    for A, B in zip(chans_a, chans_b):
        if not A and not B:
            continue
        cross = _sparse_ApiB(A, pi, B, N)
        c1, c2 = _degree_terms(A, B, pi, N)
        for i in range(N):
            row_pi = pi[i]
            ci = c1[i]
            row_cross = cross[i]
            for j in range(N):
                energy += (ci + c2[j] - 2.0 * row_cross[j]) * row_pi[j]
    return energy


def solve_fgw(
    view_a: GraphView,
    view_b: GraphView,
    affinity: Matrix,
    *,
    alpha: float = 0.7,
    max_iters: int = 60,
    tol: float = 1e-10,
    seeds: tuple[tuple[int, int, float], ...] = (),
) -> list[Matrix]:
    """Return soft couplings from every restart (unseeded first, then seeded).

    ADR-0003: at least one unseeded restart is mandatory even when seeds are
    supplied; seeds bias only the initial coupling, never constrain it.
    """
    N = max(view_a.n, view_b.n)
    chans_a = _channels(view_a, N)
    chans_b = _channels(view_b, N)
    # node cost: 1 - affinity for real pairs; padding costs a neutral 1.0 so
    # matching padding is never cheaper than a positive-affinity real match.
    M = [[1.0] * N for _ in range(N)]
    for i in range(view_a.n):
        for j in range(view_b.n):
            M[i][j] = 1.0 - affinity[i][j]

    def run(pi0: Matrix) -> Matrix:
        pi = [row[:] for row in pi0]
        e_lin = _lin_energy(M, pi, N)
        e_quad = _quad_at(chans_a, chans_b, pi, N)
        energy = (1 - alpha) * e_lin + alpha * e_quad
        for _ in range(max_iters):
            _, quad_grad = _quad_energy_and_grad(chans_a, chans_b, pi, N)
            grad = [[(1 - alpha) * M[i][j] + alpha * quad_grad[i][j]
                     for j in range(N)] for i in range(N)]
            assign = hungarian(grad)
            target = [[0.0] * N for _ in range(N)]
            for (i, j) in assign:
                target[i][j] = 1.0 / N
            delta = [[target[i][j] - pi[i][j] for j in range(N)] for i in range(N)]
            # exact line search: energy(pi + g*delta) = a*g^2 + b*g + c
            lin_d = _lin_energy(M, delta, N)
            quad_pi_d = 0.0
            for A, B in zip(chans_a, chans_b):
                if not A and not B:
                    continue
                cross = _sparse_ApiB(A, delta, B, N)
                c1, c2 = _degree_terms(A, B, delta, N)
                for i in range(N):
                    row_pi = pi[i]
                    for j in range(N):
                        quad_pi_d += (c1[i] + c2[j] - 2.0 * cross[i][j]) * row_pi[j]
            quad_dd = _quad_at(chans_a, chans_b, delta, N)
            a_coef = alpha * quad_dd
            b_coef = (1 - alpha) * lin_d + 2.0 * alpha * quad_pi_d
            if a_coef > 1e-15:
                gamma = max(0.0, min(1.0, -b_coef / (2.0 * a_coef)))
            else:
                gamma = 1.0 if b_coef < 0 else 0.0
            if gamma <= 0.0:
                break
            for i in range(N):
                row_pi, row_d = pi[i], delta[i]
                for j in range(N):
                    row_pi[j] += gamma * row_d[j]
            new_energy = a_coef * gamma * gamma + b_coef * gamma + energy
            if abs(energy - new_energy) < tol:
                energy = new_energy
                break
            energy = new_energy
        return pi

    uniform = [[1.0 / (N * N)] * N for _ in range(N)]
    couplings = [run(uniform)]
    # second unseeded restart: affinity-anchored initialisation, so mapping
    # selection always sees one semantically-honest candidate next to the
    # structure-optimal one.
    anchored = [[0.0] * N for _ in range(N)]
    total = 0.0
    for i in range(N):
        for j in range(N):
            v = (affinity[i][j] if i < view_a.n and j < view_b.n else 0.0) + 1e-6
            anchored[i][j] = v
            total += v
    couplings.append(run([[v / total for v in row] for row in anchored]))
    if seeds:
        seeded = [[1.0 / (N * N)] * N for _ in range(N)]
        for (qi, cj, support) in seeds:
            if 0 <= qi < view_a.n and 0 <= cj < view_b.n:
                boost = min(max(support, 0.0), 1.0)
                for j in range(N):
                    seeded[qi][j] *= (1.0 - 0.9 * boost)
                seeded[qi][cj] = (1.0 / N) * boost + seeded[qi][cj]
        total = sum(sum(row) for row in seeded)
        seeded = [[x / total for x in row] for row in seeded]
        couplings.append(run(seeded))
    return couplings
