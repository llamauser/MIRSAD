"""⑦ SURVEILLER — weak signals and new fraud trends (T12), on declared data only (no labels needed).

Weekly scan; each signal compares week w with the previous `baseline_weeks` weeks (as-of: weeks <= w):
  (a) nouveaux_operateurs  per HS2: declarations by companies first seen in the last 4 weeks
  (b) valeurs_basses       per HS4: share of declarations priced >= 2 robust sd below comparables (z_uv <= -2)
  (c) declarant_eventail   per declarant: number of distinct recently-new companies it declares for
An alert fires when z >= z_min and the count >= min_count. Thresholds are fixed in config.yaml BEFORE any
evaluation (docs/decisions.md) so they are not tuned on the results.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _z(cur: pd.Series, base: pd.DataFrame) -> pd.DataFrame:
    mu = base.mean(axis=1).reindex(cur.index).fillna(0)
    sd = base.std(axis=1).reindex(cur.index).fillna(0)
    denom = np.maximum.reduce([sd.values, np.sqrt(mu.values), np.ones(len(mu))])
    return pd.DataFrame({"valeur": cur, "reference": mu, "z": (cur - mu) / denom})


def scan(static: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    tc = cfg.get("trends", {})
    B, zmin = tc.get("baseline_weeks", 8), tc.get("z_min", 3.0)
    first = static.groupby("importer").week.min()
    d = static.assign(recent=(static.week - static.importer.map(first)) < 4,
                      low=static.z_uv <= -2)
    weeks = sorted(d.week.unique())
    # weekly aggregates (declared data only)
    a = d[d.recent].groupby(["hs2", "week"]).size().unstack(fill_value=0).reindex(columns=weeks, fill_value=0)
    nb4 = d.groupby(["hs4", "week"]).size().unstack(fill_value=0).reindex(columns=weeks, fill_value=0)
    lo4 = d[d.low].groupby(["hs4", "week"]).size().unstack(fill_value=0).reindex(columns=weeks, fill_value=0)
    c = (d[d.recent].groupby(["declarant", "week"]).importer.nunique().unstack(fill_value=0)
         .reindex(columns=weeks, fill_value=0))
    rows = []
    for i, w in enumerate(weeks):
        if i < B:
            continue
        prev = weeks[i - B:i]
        za = _z(a[w], a[prev])
        for k, r in za[(za.z >= zmin) & (za.valeur >= tc.get("min_count_a", 10))].iterrows():
            rows.append(("nouveaux_operateurs", "hs2", k, w, r.valeur, r.reference, r.z))
        share = (lo4[w] / nb4[w].replace(0, np.nan)).fillna(0)
        s0 = (lo4[prev].sum(axis=1) / nb4[prev].sum(axis=1).replace(0, np.nan)).fillna(0).clip(0.01, 0.99)
        zb = (share - s0) / np.sqrt(s0 * (1 - s0) / nb4[w].clip(lower=1))
        ok = (zb >= zmin) & (lo4[w] >= tc.get("min_count_b", 8)) & (nb4[w] >= 20)
        for k in zb[ok].index:
            rows.append(("valeurs_basses", "hs4", k, w, float(share[k]), float(s0[k]), float(zb[k])))
        zc = _z(c[w], c[prev])
        for k, r in zc[(zc.z >= zmin) & (zc.valeur >= tc.get("min_count_c", 5))].iterrows():
            rows.append(("declarant_eventail", "declarant", k, w, r.valeur, r.reference, r.z))
    al = pd.DataFrame(rows, columns=["signal", "cle_type", "cle", "week", "valeur", "reference", "z"])
    al["alert_id"] = [f"ALERT-{s[:4].upper()}-{k}-S{w}" for s, k, w in zip(al.signal, al.cle, al.week)]
    return al


def active_mask(batch: pd.DataFrame, alerts: pd.DataFrame, week: int, persist: int = 2) -> np.ndarray:
    """Rows of the batch matching an alert raised in weeks (week-persist, week] — used to steer exploration."""
    if alerts is None or not len(alerts):
        return np.zeros(len(batch), bool)
    act = alerts[(alerts.week <= week) & (alerts.week > week - persist)]
    m = np.zeros(len(batch), bool)
    for col, kind in (("hs2", "hs2"), ("hs4", "hs4"), ("declarant", "declarant")):
        keys = set(act[act.cle_type == kind].cle)
        if keys:
            m |= batch[col].isin(keys).values
    return m
