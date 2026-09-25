"""Feature engineering.

Two families, both strictly time-respecting:
- *static* features use only declared data (values, entities) of past weeks.
  Declared values are observed for every declaration, inspected or not, so
  they may use all past rows. Precomputed once per week (`build_static`).
- *label* features (smoothed risk profiles) use only labels of past rows that
  were actually inspected (`risk_profiles(revealed, batch)`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

MAD_K = 1.4826
EPS = 1e-9
RATIO_COLS = ["l_uv", "l_uv_kg", "tax_rt", "fob_cif", "l_kg_unit"]
Z_COLS = {"l_uv": "z_uv", "l_uv_kg": "z_uv_kg", "tax_rt": "z_tax_rt", "l_kg_unit": "z_kg_unit"}
RISK_KEYS = {
    "risk_importer": ["importer"],
    "risk_declarant": ["declarant"],
    "risk_office": ["office"],
    "risk_country": ["country"],
    "risk_hs6": ["hs6"],
    "risk_imp_hs4": ["importer", "hs4"],
}
STATIC_FEATURES = (RATIO_COLS + ["l_cif", "l_qty"] + list(Z_COLS.values())
                   + ["hist_count_importer", "hist_count_declarant", "days_since_first",
                      "is_new_importer", "is_new_combo", "iso_score"])
MODEL_FEATURES = STATIC_FEATURES + list(RISK_KEYS) + ["n_inspected_importer"]


def _safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.full_like(a, np.nan)
    ok = np.isfinite(a) & np.isfinite(b) & (b > 0)
    out[ok] = a[ok] / b[ok]
    return out


def add_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Row-level ratios (no history needed). Log-transformed and clipped."""
    df = df.copy()
    has = lambda c: c in df.columns  # noqa: E731
    df["l_uv"] = np.log1p(_safe_div(df.cif, df.quantity)) if has("quantity") else np.nan
    df["l_uv_kg"] = np.log1p(_safe_div(df.cif, df.weight)) if has("weight") else np.nan
    df["tax_rt"] = np.clip(_safe_div(df.taxes, df.cif), 0, 5) if has("taxes") else np.nan
    df["fob_cif"] = np.clip(_safe_div(df.fob, df.cif), 0, 5) if has("fob") else np.nan
    df["l_kg_unit"] = (np.log1p(_safe_div(df.weight, df.quantity))
                       if has("weight") and has("quantity") else np.nan)
    df["l_cif"] = np.log1p(df.cif.clip(lower=0))
    df["l_qty"] = np.log1p(df.quantity.clip(lower=0)) if has("quantity") else np.nan
    return df


def _group_stats(hist: pd.DataFrame, keys: list[str], col: str) -> pd.DataFrame:
    g = hist.groupby(keys, observed=True)[col]
    med = g.median().rename("med")
    mad = hist[keys + [col]].merge(med.reset_index(), on=keys)
    mad = (mad[col] - mad["med"]).abs().groupby([mad[k] for k in keys]).median().rename("mad")
    n = g.count().rename("n")
    return pd.concat([med, mad, n], axis=1).reset_index()


def robust_z(history: pd.DataFrame, batch: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    """Robust z-scores with back-off (HS6,country) -> HS6 -> HS4 -> HS2 -> global."""
    out = pd.DataFrame(index=batch.index)
    levels = [["hs6", "country"], ["hs6"], ["hs4"], ["hs2"]]
    levels = [lv for lv in levels if all(k in batch.columns for k in lv)]
    for col, zname in Z_COLS.items():
        med = pd.Series(np.nan, index=batch.index)
        mad = pd.Series(np.nan, index=batch.index)
        level = pd.Series("", index=batch.index)
        h = history[history[col].notna()] if len(history) else history
        if len(h):
            for lv in levels:
                st = _group_stats(h, lv, col)
                st = st[st.n >= min_n]
                m = batch[lv].merge(st, on=lv, how="left")
                m.index = batch.index
                fill = med.isna() & m.med.notna()
                med[fill], mad[fill], level[fill] = m.med[fill], m.mad[fill], "/".join(lv)
            fill = med.isna()
            med[fill] = h[col].median()
            mad[fill] = (h[col] - h[col].median()).abs().median()
            level[fill] = "global"
            z = (batch[col] - med) / (MAD_K * mad + 1e-6)
            out[zname] = z.clip(-20, 20).fillna(0.0)
        else:
            out[zname] = 0.0
        out[zname + "_med"] = med
        out[zname + "_level"] = level
    return out


def history_features(history: pd.DataFrame, batch: pd.DataFrame) -> pd.DataFrame:
    """Entity history (declared data only)."""
    out = pd.DataFrame(index=batch.index)
    if len(history):
        cnt_imp = history.importer.value_counts()
        cnt_dec = history.declarant.value_counts() if "declarant" in history else pd.Series(dtype=float)
        first = history.groupby("importer").date.min()
        combos = set(zip(history.importer, history.hs4))
    else:
        cnt_imp = cnt_dec = pd.Series(dtype=float)
        first = pd.Series(dtype="datetime64[ns]")
        combos = set()
    out["hist_count_importer"] = batch.importer.map(cnt_imp).fillna(0).astype(float)
    out["hist_count_declarant"] = (batch.declarant.map(cnt_dec).fillna(0).astype(float)
                                   if "declarant" in batch else 0.0)
    if len(first):
        fs = batch[["importer"]].merge(first.rename("first").reset_index(), on="importer", how="left")["first"]
        out["days_since_first"] = (batch.date.values - fs.values).astype("timedelta64[D]").astype(float)
        out["days_since_first"] = out["days_since_first"].fillna(0.0)
    else:
        out["days_since_first"] = 0.0
    out["is_new_importer"] = (out.hist_count_importer == 0).astype(float)
    out["is_new_combo"] = np.array([(i, h) not in combos for i, h in zip(batch.importer, batch.hs4)],
                                   dtype=float)
    return out


ISO_COLS = ["l_uv", "l_uv_kg", "tax_rt", "fob_cif", "l_kg_unit", "l_cif"]


def iso_scores(history: pd.DataFrame, batch: pd.DataFrame, seed: int = 0, max_fit: int = 20000):
    cols = [c for c in ISO_COLS if c in batch.columns and batch[c].notna().any()]
    if len(history) < 200 or not cols:
        return np.zeros(len(batch))
    h = history[cols].fillna(history[cols].median())
    if len(h) > max_fit:
        h = h.sample(max_fit, random_state=seed)
    iso = IsolationForest(n_estimators=100, random_state=seed, n_jobs=1).fit(h.values)
    b = batch[cols].fillna(history[cols].median())
    return -iso.score_samples(b.values)  # higher = more anomalous


def build_static(df: pd.DataFrame, min_n: int = 30, verbose: bool = True) -> pd.DataFrame:
    """For every week w, compute static features of week-w rows from weeks < w only."""
    df = add_ratios(df)
    parts = []
    for w in sorted(df.week.unique()):
        hist = df[df.week < w]
        batch = df[df.week == w]
        z = robust_z(hist, batch, min_n)
        hf = history_features(hist, batch)
        f = pd.concat([batch, z, hf], axis=1)
        f["iso_score"] = iso_scores(hist, batch, seed=int(w))
        parts.append(f)
        if verbose and w % 10 == 0:
            print(f"  static features week {w}")
    return pd.concat(parts).sort_index()


def risk_profiles(revealed: pd.DataFrame, batch: pd.DataFrame, alpha: float = 10,
                  p0: float | None = None) -> pd.DataFrame:
    """Smoothed fraud rate per entity from *revealed* (inspected) past rows only."""
    out = pd.DataFrame(index=batch.index)
    if p0 is None:
        p0 = float(revealed.label_fraud.mean()) if len(revealed) else 0.05
    for name, keys in RISK_KEYS.items():
        if not all(k in batch.columns for k in keys):
            out[name] = p0
            continue
        if len(revealed):
            g = revealed.groupby(keys, observed=True).label_fraud.agg(["sum", "count"]).reset_index()
            m = batch[keys].merge(g, on=keys, how="left")
            s, c = m["sum"].fillna(0).values, m["count"].fillna(0).values
        else:
            s = c = np.zeros(len(batch))
        out[name] = (s + alpha * p0) / (c + alpha)
        if name == "risk_importer":
            out["n_inspected_importer"] = c
    return out
