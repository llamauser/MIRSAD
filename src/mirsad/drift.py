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


def _undervalue(df, idx, f):
    orig_taxes = df.loc[idx, "taxes"].copy()
    df.loc[idx, "cif"] = df.loc[idx, "cif"] * f
    if "fob" in df:
        df.loc[idx, "fob"] = df.loc[idx, "fob"] * f
    df.loc[idx, "taxes"] = (orig_taxes * f).round()
    df.loc[idx, "label_fraud"] = 1
    df.loc[idx, "label_revenue"] = orig_taxes - df.loc[idx, "taxes"]
    df.loc[idx, "scheme"] = "injected"


def inject_turncoat(df: pd.DataFrame, cfg: dict, seed: int = 12345) -> tuple[pd.DataFrame, dict]:
    """Established companies with a clean record start undervaluing half of their declarations from W0."""
    d = cfg["drift"]
    df = df.copy()
    df["scheme"] = "none"
    w0, f = int(d["start_week"]), float(d["undervaluation_factor"])
    rng = np.random.default_rng(seed)
    before = df[df.week < w0].groupby("importer").agg(n=("id", "size"), fr=("label_fraud", "mean"))
    after = df[df.week >= w0].groupby("importer").size().rename("n_after")
    cand = before.join(after, how="inner")
    cand = cand[(cand.n >= 15) & (cand.fr == 0) & (cand.n_after >= 10)]
    target = int(d.get("target_rows", 1900))
    chosen, total = [], 0
    for imp in rng.permutation(cand.index.values):
        chosen.append(imp)
        total += int(cand.loc[imp, "n_after"] * 0.5)
        if total >= target:
            break
    pool = df.index[(df.week >= w0) & df.importer.isin(chosen) & (df.label_fraud == 0)]
    idx = np.sort(rng.choice(pool, size=min(len(pool), total), replace=False))
    _undervalue(df, idx, f)
    return df, {"scenario": "turncoat", "start_week": w0, "n_companies": len(chosen), "n_rows": int(len(idx)),
                "injected_revenue_total": float(df.loc[idx, "label_revenue"].sum()),
                "note": "Scénario simulé : des entreprises établies au passé propre commencent à sous-évaluer."}


def inject_network(df: pd.DataFrame, cfg: dict, seed: int = 12345) -> tuple[pd.DataFrame, dict]:
    """New companies route undervalued declarations through ONE existing declarant (a facilitator network)."""
    d = cfg["drift"]
    df = df.copy()
    df["scheme"] = "none"
    w0, f = int(d["start_week"]), float(d["undervaluation_factor"])
    rng = np.random.default_rng(seed)
    decl = df[df.week < w0].groupby("declarant").size()
    declarant = str(rng.choice(decl[(decl >= 50) & (decl <= 200)].index.values))
    hs2 = str(d.get("network_hs2", "85"))
    pool = df.index[(df.week >= w0) & (df.hs2 == hs2) & (df.label_fraud == 0)]
    n = min(len(pool), int(d.get("target_rows", 1900)))
    idx = np.sort(rng.choice(pool, size=n, replace=False))
    imps = [f"IMPNET{i:03d}" for i in range(int(d["n_new_importers"]))]
    df.loc[idx, "importer"] = rng.choice(imps, size=n)
    df.loc[idx, "declarant"] = declarant
    _undervalue(df, idx, f)
    return df, {"scenario": "network", "start_week": w0, "hs2": hs2, "declarant": declarant, "n_rows": int(n),
                "n_new_importers": len(imps), "injected_revenue_total": float(df.loc[idx, "label_revenue"].sum()),
                "note": "Scénario simulé : de nouvelles entreprises passent toutes par un même déclarant existant."}


SCENARIOS = {"front": None, "turncoat": inject_turncoat, "network": inject_network}


def inject(df: pd.DataFrame, cfg: dict, seed: int = 12345, scenario: str = "front") -> tuple[pd.DataFrame, dict]:
    if scenario != "front":
        return SCENARIOS[scenario](df, cfg, seed)
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
        "scenario": "front", "enabled": True, "start_week": w0, "hs2": hs2, "n_rows": int(n),
        "share_of_chapter_rows_from_w0": float(d["share"]),
        "n_new_importers": len(new_imps), "undervaluation_factor": f,
        "injected_revenue_total": float(df.loc[idx, "label_revenue"].sum()),
        "rows_per_week_mean": float(n / max(1, df.week.max() - w0 + 1)),
        "note": "Scénario de fraude simulé (ajouté par l'équipe), pas une donnée réelle.",
    }
    return df, log
