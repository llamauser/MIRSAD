"""② CONNAÎTRE — dynamic company compliance score (T20) and ③ SEGMENTER — operator tiers (T5).

Company score = Beta posterior of the company's fraud rate, from *inspected* past declarations only:
    prior    Beta(α·p0, α·(1−p0))       p0 = fraud rate among RANDOM inspections (unbiased base rate)
    update   a += Σ w·fraud, b += Σ w·(1−fraud),   w = 0.5 ** (age_weeks / half_life)   (time decay)
The posterior mean equals the smoothed rate used before; what is new is the uncertainty (sd, n_eff),
the decay (old behaviour fades), the trend, and a link signal (risk of the declarants the company uses).

Segments (WCO-style compliance tiers, from score and certainty):
    Surveillé  little known (n_eff < N_MIN)            -> exploration budget
    Critique   known and risky (mean >= HIGH × p0)      -> priority
    Confiance  known and compliant (mean <= LOW × p0)   -> mostly green + random audits
    Standard   everything else
Everything is computed "as of" a week: declared data of past weeks, labels of past inspected rows only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEGMENTS = ["Confiance", "Standard", "Surveillé", "Critique"]
ENTITY_FEATURES = ["ent_mean", "ent_sd", "ent_neff", "ent_trend", "link_risk"]


def base_rate(revealed: pd.DataFrame, default: float = 0.076) -> float:
    """Unbiased fraud base rate: only randomly selected inspections (warm start + random audits)."""
    if "rev_src" in revealed:
        r = revealed[revealed.rev_src.isin(["warm", "audit"])]
        if len(r) >= 50:
            return float(r.label_fraud.mean())
    return default


def posterior(revealed: pd.DataFrame, key: str, week: int, p0: float, alpha: float = 10,
              half_life: float = 12) -> pd.DataFrame:
    """Beta posterior per entity as of `week` (rows of weeks < week only)."""
    r = revealed[revealed.week < week]
    if not len(r):
        return pd.DataFrame(columns=["a", "b", "mean", "sd", "n_eff"])
    w = 0.5 ** ((week - r.week.values) / half_life)
    g = pd.DataFrame({key: r[key].values, "w": w, "wy": w * r.label_fraud.values}).groupby(key)[["w", "wy"]].sum()
    a = alpha * p0 + g.wy
    b = alpha * (1 - p0) + (g.w - g.wy)
    out = pd.DataFrame({"a": a, "b": b, "n_eff": g.w})
    out["mean"] = a / (a + b)
    out["sd"] = np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return out


def link_risk(history: pd.DataFrame, dec_post: pd.DataFrame, importers: pd.Index, p0: float) -> pd.Series:
    """Risk propagated through the graph: usage-weighted mean posterior of the declarants a company used."""
    if not len(history) or not len(dec_post):
        return pd.Series(p0, index=importers)
    e = history.groupby(["importer", "declarant"]).size().rename("n").reset_index()
    e = e[e.importer.isin(importers)]
    e["m"] = e.declarant.map(dec_post["mean"]).fillna(p0)
    agg = (e.m * e.n).groupby(e.importer).sum() / e.n.groupby(e.importer).sum()
    return agg.reindex(importers).fillna(p0)


def segment(mean, n_eff, p0, n_min: float = 2.0, high: float = 2.0, low: float = 0.75):
    mean, n_eff = np.asarray(mean, float), np.asarray(n_eff, float)
    seg = np.full(len(mean), "Standard", dtype=object)
    known = n_eff >= n_min
    seg[~known] = "Surveillé"
    seg[known & (mean >= high * p0)] = "Critique"
    seg[known & (mean <= low * p0)] = "Confiance"
    return seg


def company_table(revealed: pd.DataFrame, history: pd.DataFrame, week: int, cfg: dict,
                  importers: pd.Index | None = None) -> pd.DataFrame:
    """Importer-level score table as of `week` (used by the batch features, the register and the app)."""
    ec = cfg.get("entity", {})
    alpha, hl = ec.get("alpha", 10), ec.get("half_life", 12)
    p0 = base_rate(revealed)
    imp = posterior(revealed, "importer", week, p0, alpha, hl)
    old = posterior(revealed, "importer", week - 4, p0, alpha, hl)
    dec = posterior(revealed, "declarant", week, p0, alpha, hl)
    if importers is None:
        importers = pd.Index(history.importer.unique()) if len(history) else pd.Index([])
    t = pd.DataFrame(index=importers)
    t["ent_mean"] = imp["mean"].reindex(importers).fillna(p0)
    t["ent_sd"] = imp["sd"].reindex(importers)
    prior_sd = np.sqrt(p0 * (1 - p0) / (alpha + 1))
    t["ent_sd"] = t.ent_sd.fillna(prior_sd)
    t["ent_neff"] = imp["n_eff"].reindex(importers).fillna(0.0)
    t["ent_a"] = imp["a"].reindex(importers).fillna(alpha * p0)
    t["ent_b"] = imp["b"].reindex(importers).fillna(alpha * (1 - p0))
    t["ent_trend"] = t.ent_mean - old["mean"].reindex(importers).fillna(p0)
    t["link_risk"] = link_risk(history, dec, importers, p0)
    t["segment"] = segment(t.ent_mean, t.ent_neff, p0, ec.get("n_min", 2.0), ec.get("high", 2.0), ec.get("low", 0.75))
    t["score_0_100"] = (100 * t.ent_mean).round(1)
    t.attrs["p0"] = p0
    return t


def batch_features(revealed, history, batch, week, cfg) -> pd.DataFrame:
    t = company_table(revealed, history, week, cfg, pd.Index(batch.importer.unique()))
    f = t.reindex(batch.importer.values)[ENTITY_FEATURES + ["segment", "ent_a", "ent_b"]]
    f.index = batch.index
    return f
