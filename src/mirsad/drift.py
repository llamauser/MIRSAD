"""Injected new fraud scheme (SIMULATED scenario).

From week W0, a set of brand-new importers takes over a share of one HS chapter's
declarations and undervalues them. These rows are all frauds. No model trained on
past labels has ever seen these importers, so only exploration can find them early.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pick_chapter(df: pd.DataFrame, before_week: int) -> str:
    h = df[df.week < before_week]
    g = h.groupby("hs2").agg(n=("id", "size"), fr=("label_fraud", "mean"))
    cand = g[g.fr < g.fr.median()]
    return str(cand.n.idxmax())


def inject(df: pd.DataFrame, cfg: dict, seed: int = 12345) -> tuple[pd.DataFrame, dict]:
    d = cfg["drift"]
    df = df.copy()
    df["scheme"] = "none"
    if not d.get("enabled", True):
        return df, {"enabled": False}
    w0 = int(d["start_week"])
    hs2 = pick_chapter(df, w0) if d.get("hs2", "auto") == "auto" else str(d["hs2"]).zfill(2)
    rng = np.random.default_rng(seed)
    pool = df.index[(df.week >= w0) & (df.hs2 == hs2) & (df.label_fraud == 0)]
    n = int(round(d["share"] * ((df.week >= w0) & (df.hs2 == hs2)).sum()))
    n = min(n, len(pool))
    idx = np.sort(rng.choice(pool, size=n, replace=False))
    new_imps = [f"IMPNEW{i:03d}" for i in range(int(d["n_new_importers"]))]
    f = float(d["undervaluation_factor"])
    orig_taxes = df.loc[idx, "taxes"].copy()
    df.loc[idx, "importer"] = rng.choice(new_imps, size=n)
    df.loc[idx, "cif"] = df.loc[idx, "cif"] * f
    if "fob" in df:
        df.loc[idx, "fob"] = df.loc[idx, "fob"] * f
    df.loc[idx, "taxes"] = (orig_taxes * f).round()
    df.loc[idx, "label_fraud"] = 1
    df.loc[idx, "label_revenue"] = orig_taxes - df.loc[idx, "taxes"]
    df.loc[idx, "scheme"] = "injected"
    log = {
        "enabled": True, "start_week": w0, "hs2": hs2, "n_rows": int(n),
        "share_of_chapter_rows_from_w0": float(d["share"]),
        "n_new_importers": len(new_imps), "undervaluation_factor": f,
        "injected_revenue_total": float(df.loc[idx, "label_revenue"].sum()),
        "rows_per_week_mean": float(n / max(1, df.week.max() - w0 + 1)),
        "note": "Scénario de fraude simulé (ajouté par l'équipe), pas une donnée réelle.",
    }
    return df, log
