"""Exact rectangular assignment (Jonker-Volgenant style shortest augmenting path).

Stdlib-only. Minimizes total cost. Rectangular inputs are handled by
augmenting-path construction directly (no explicit padding); unmatched
rows/columns are expressed by the caller through explicit dummy columns/rows
carrying the unmatched cost, so "unmatched" stays a visible modeling choice.
"""

from __future__ import annotations

INF = float("inf")


def solve(cost: list[list[float]]) -> list[tuple[int, int]]:
    """Return the minimum-cost assignment as (row, col) pairs.

    Requires len(cost) <= len(cost[0]); every row is assigned. Deterministic.
    """
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if n > m:
        raise ValueError("hungarian: rows must not exceed columns; pad with dummy columns")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)          # p[j] = row assigned to column j (1-based; 0 = free)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = []
    for j in range(1, m + 1):
        if p[j]:
            out.append((p[j] - 1, j - 1))
    out.sort()
    return out
