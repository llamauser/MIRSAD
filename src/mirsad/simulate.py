"""Leakage-safe weekly simulation with selective labels.

Each week: features from the past -> train on inspected rows only -> score the week
-> select under budget -> reveal labels of the selected rows only -> next week.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import risk_profiles
from .model import RiskModel
from .policy import LANE_ORANGE, LANE_ROUGE, LANE_VERT, NEEDS_MODEL, assign_lanes, select


def run(static: pd.DataFrame, cfg: dict, policy: str, r: float, eps: float, seed: int,
        keep_week: int | None = None, audit: bool = False, end_week: int | None = None):
    sc, fc, mc = cfg["simulation"], cfg["features"], cfg["model"]
    rng = np.random.default_rng(seed)
    alpha = fc["alpha"]
    weeks = sorted(static.week.unique())
    end_week = end_week or sc["end_week"]
    revealed_parts: list[pd.DataFrame] = []
    rows, audits, keep = [], [], {}
    model = None
    for w in weeks:
        if w > end_week:
            break
        b = static[static.week == w]
        revealed = pd.concat(revealed_parts) if revealed_parts else b.iloc[0:0]
        b = b.join(risk_profiles(revealed, b, alpha))
        if w < sc["start_week"]:  # warm start: random inspections only
            n_rev = int(round(sc["warm_reveal_share"] * len(b)))
            pos = rng.choice(len(b), size=n_rev, replace=False)
            revealed_parts.append(b.iloc[pos])
            continue
        if policy in NEEDS_MODEL:
            if model is None or (w - sc["start_week"]) % sc.get("retrain_every", 1) == 0:
                model = RiskModel(n_estimators=mc["n_estimators"], learning_rate=mc["learning_rate"],
                                  num_leaves=mc["num_leaves"], seed=mc["seed"] + seed)
                model.fit(revealed, calib_week=int(revealed.week.max()))
                if audit:
                    audits.append({"week": w, "train_ids": set(revealed.id),
                                   "train_max_week": int(revealed.week.max())})
            b = b.join(model.score(b))
        else:
            b = b.assign(p=np.nan, r_hat=np.nan, er=np.nan)
        k = int(round(r * len(b)))
        sel, score = select(policy, b, k, eps, rng)
        lanes = assign_lanes(len(b), sel, score, k_orange=k)
        y, rev = b.label_fraud.values, b.label_revenue.values
        inj = (b.scheme.values == "injected")
        red, org, vert = lanes == LANE_ROUGE, lanes == LANE_ORANGE, lanes == LANE_VERT
        rows.append({
            "week": w, "N": len(b), "k": int(red.sum()),
            "fraud_total": int(y.sum()), "fraud_sel": int(y[red].sum()),
            "rev_total": float(rev.sum()), "rev_sel": float(rev[red].sum()),
            "rev_orange": float(rev[org].sum()), "rev_vert": float(rev[vert].sum()),
            "fraud_vert": int(y[vert].sum()), "n_vert": int(vert.sum()),
            "inj_total": int(inj.sum()), "inj_sel": int((inj & red).sum()),
            "rev_inj_total": float(rev[inj].sum()), "rev_inj_sel": float(rev[inj & red].sum()),
            "rev_hist_total": float(rev[~inj].sum()), "rev_hist_sel": float(rev[~inj & red].sum()),
            "n_new_imp_sel": int(b.is_new_importer.values[red].sum()),
        })
        if keep_week is not None and w == keep_week:
            keep = {"batch": b.assign(lane=lanes), "revealed": revealed, "model": model}
        revealed_parts.append(b.iloc[sel].drop(columns=["p", "r_hat", "er"]))
    out = pd.DataFrame(rows).assign(policy=policy, r=r, eps=eps, seed=seed)
    return out, keep, audits


def summarize(weekly: pd.DataFrame, w0: int) -> dict:
    s = weekly.sum(numeric_only=True)
    after = weekly[weekly.week >= w0].sum(numeric_only=True)
    return {
        "precision_at_k": s.fraud_sel / max(s.k, 1),
        "recall": s.fraud_sel / max(s.fraud_total, 1),
        "revenue_at_k": s.rev_sel / max(s.rev_total, 1),
        "revenue_hist_at_k": s.rev_hist_sel / max(s.rev_hist_total, 1),
        "tnd_per_inspection": s.rev_sel / max(s.k, 1),
        "injected_recall_rev": after.rev_inj_sel / max(after.rev_inj_total, 1),
        "injected_recall_n": after.inj_sel / max(after.inj_total, 1),
        "false_green_fraud": s.fraud_vert / max(s.fraud_total, 1),
        "false_green_rev": s.rev_vert / max(s.rev_total, 1),
        "share_vert": s.n_vert / max(s.N, 1),
    }
