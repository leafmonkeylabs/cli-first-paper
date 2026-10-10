"""Contrasts for the follow-ups (paper Section 7), with the paper's interval method.

A contrast is a weighted sum of configurations' mean log costs in each cell,
for example removing options averaged over whether output shapes are present:
  1/2 (noopts - full) + 1/2 (names - noout).
It is estimated per cell and averaged over cells. Its variance sums the
configurations' run variances (Welch), and the degrees of freedom come from
Satterthwaite, as for the paper's "these tasks" intervals (stats.welch).

The p-value is two-sided, from the t distribution, via the regularized
incomplete beta function. Holm adjustment is stats.holm.

A cross-wave contrast (the ratio of ratios) uses the same formula over cells
present in both waves. For a configuration and its baseline it is:
  (a - base) in wave 1  -  (a - base) in wave 2.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, variance

import stats


def log_cells(rows: list[dict], cost=lambda r: r["cost_usd"]) -> dict:
    c = defaultdict(list)
    for r in rows:
        c[(r["model"], stats.FAMILY[r["task"]], r["task"], r["size"], r["arm"])].append(math.log(cost(r)))
    return c


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    return _betainc(df / 2, 0.5, df / (df + t * t))


def _combine(ests: list[float], parts: list[tuple[float, float]], n: int) -> dict:
    d = mean(ests)
    var = sum(v for v, _ in parts) / n / n
    den = sum((v / n / n) ** 2 / df for v, df in parts if df > 0)
    df = var ** 2 / den if den else 1.0
    se = math.sqrt(var)
    q = stats.t_quantile(0.975, df)
    return {"ratio": round(math.exp(d), 3), "lo": round(math.exp(d - q * se), 3), "hi": round(math.exp(d + q * se), 3),
            "df": round(df, 1), "p": t_two_sided_p(d / se, df) if se > 0 else 1.0, "cells": n}


def contrast(c: dict, model: str, family: str, weights: dict[str, float]) -> dict:
    keys = sorted({(t, s) for (m, f, t, s, _a) in c if m == model and f == family})
    ests, parts = [], []
    for t, s in keys:
        if not all((model, family, t, s, a) in c for a in weights):
            continue
        e = 0.0
        for a, w in weights.items():
            xs = c[(model, family, t, s, a)]
            e += w * mean(xs)
            parts.append((w * w * variance(xs) / len(xs), len(xs) - 1))
        ests.append(e)
    return _combine(ests, parts, len(ests))


def cross_wave(c1: dict, c2: dict, model: str, family: str, arm: str, base: str = "mcp",
               base2: str | None = None) -> dict:
    """(arm vs base in wave 1) relative to (arm vs base2 in wave 2); base2 defaults to base."""
    base2 = base2 or base
    keys = sorted({(t, s) for (m, f, t, s, _a) in c1 if m == model and f == family})
    ests, parts = [], []
    for t, s in keys:
        ks = [(c1, arm, 1), (c1, base, -1), (c2, arm, -1), (c2, base2, 1)]
        if not all((model, family, t, s, a) in cc for cc, a, _ in ks):
            continue
        e = 0.0
        for cc, a, w in ks:
            xs = cc[(model, family, t, s, a)]
            e += w * mean(xs)
            parts.append((variance(xs) / len(xs), len(xs) - 1))
        ests.append(e)
    return _combine(ests, parts, len(ests))


def holm_apply(results: list[dict]) -> None:
    for r, p in zip(results, stats.holm([r["p"] for r in results])):
        r["p_holm"] = round(p, 4)
        r["p"] = round(r["p"], 4)
