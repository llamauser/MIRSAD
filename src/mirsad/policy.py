"""Selection policies under a weekly inspection budget k = r * N, and lanes."""
from __future__ import annotations

import numpy as np
import pandas as pd

# mirsad = rank by expected recovered revenue ER = p * R_hat; eps > 0 adds exploration.
# model_p = ablation ranking by probability only.
POLICIES = ["random", "rules", "model_p", "mirsad"]
NEEDS_MODEL = {"model_p", "mirsad"}
LANE_ROUGE, LANE_ORANGE, LANE_VERT = "Rouge", "Orange", "Vert"


def rank_score(policy: str, b: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Deterministic ranking score used for exploitation and for the Orange lane."""
    if policy == "random":
        return rng.random(len(b))
    if policy == "rules":
        # highest smoothed importer risk, ties broken by lowest declared tax rate
        return b.risk_importer.values - 1e-3 * np.nan_to_num(b.tax_rt.values, nan=1.0)
    if policy == "model_p":
        return b.p.values
    return b.er.values  # mirsad


def explore_weight(b: pd.DataFrame) -> np.ndarray:
    return b.p.values * (1 - b.p.values) + 0.5 * b.is_new_combo.values + 0.5 * b.is_new_importer.values


def select(policy: str, b: pd.DataFrame, k: int, eps: float, rng: np.random.Generator):
    """Return (positions selected, ranking score). Positions index into b."""
    n = len(b)
    k = min(k, n)
    score = rank_score(policy, b, rng)
    if policy != "mirsad" or eps <= 0:
        return np.argsort(-score, kind="stable")[:k], score
    k_exp = int(round(eps * k))
    exploit = np.argsort(-score, kind="stable")[: k - k_exp]
    rest = np.setdiff1d(np.arange(n), exploit)
    if k_exp and len(rest):
        w = explore_weight(b.iloc[rest]) + 1e-9
        explore = rng.choice(rest, size=min(k_exp, len(rest)), replace=False, p=w / w.sum())
    else:
        explore = np.array([], dtype=int)
    return np.concatenate([exploit, explore]), score


def assign_lanes(n: int, selected: np.ndarray, score: np.ndarray, k_orange: int) -> np.ndarray:
    lanes = np.full(n, LANE_VERT, dtype=object)
    lanes[selected] = LANE_ROUGE
    mask = np.ones(n, bool)
    mask[selected] = False
    rest = np.where(mask)[0]
    orange = rest[np.argsort(-score[rest], kind="stable")[:k_orange]]
    lanes[orange] = LANE_ORANGE
    return lanes
