"""The worked example of the cost model (Section 4.2, Table 1).

Input-token equivalents for k dependent operations:
  direct calls, uncached: (k+1)(S+u) + sum_i (k+1-i)(a_i + r_i)
  direct calls, cached:   w*P_1 + rho*sum_{j<=k} P_j + w*sum_i (a_i + r_i),
                          with P_j = S + u + sum_{i<j} (a_i + r_i)
  pipeline, uncached:     2(S+u) + c + f
  pipeline, cached:       w(S+u+c+f) + rho(S+u)
w = cache-write multiplier (1.25), rho = cache-read multiplier (0.1).
Usage: python cost_model.py > ../data/cost_model.csv
"""
from __future__ import annotations

W, RHO = 1.25, 0.1


def direct(S, u, k, a, r):
    steps = [a + r] * k
    uncached = (k + 1) * (S + u) + sum((k + 1 - i) * steps[i - 1] for i in range(1, k + 1))
    P = [S + u + sum(steps[: j - 1]) for j in range(1, k + 1)]
    cached = W * P[0] + RHO * sum(P) + W * sum(steps)
    return k + 1, uncached, cached


def pipeline(S, u, c, f):
    return 2, 2 * (S + u) + c + f, W * (S + u + c + f) + RHO * (S + u)


def main() -> None:
    S, u, k, a, r, c, f = 10_000, 1_000, 5, 100, 2_000, 400, 200
    print("setting,passes,uncached_tokens,cached_tokens")
    for name, (p, unc, cac) in [("direct tool calls", direct(S, u, k, a, r)),
                                ("CLI pipeline", pipeline(S, u, c, f)),
                                ("CLI pipeline S=1k", pipeline(1_000, u, c, f))]:
        print(f"{name},{p},{unc:.0f},{cac:.0f}")


if __name__ == "__main__":
    main()
