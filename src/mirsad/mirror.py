"""Mirror statistics (UN Comtrade, real Tunisia data): Tunisia imports vs partner exports.

M = Tunisia imports from partner (CIF, reported by Tunisia)
X = partner exports to Tunisia (FOB, reported by partner)
M_fob = M_cif / (1 + c); gap = log(X / M_fob); leak = max(0, X - M_fob)
A macro PRIORITISATION indicator, not proof: timing, transit/re-exports, CIF/FOB,
classification differences all create gaps.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

PARTNERS = {"China": 156, "Türkiye": 792, "Italy": 380, "France": 251, "Germany": 276,
            "Spain": 724, "Algeria": 12, "Libya": 434}
PARTNERS_FR = {"China": "Chine", "Türkiye": "Turquie", "Italy": "Italie", "France": "France",
               "Germany": "Allemagne", "Spain": "Espagne", "Algeria": "Algérie", "Libya": "Libye"}
TUNISIA = 788


def _fetch(reporter: int, partner: int, flow: str, year: int) -> pd.DataFrame | None:
    import comtradeapicall as c
    key = os.environ.get("COMTRADE_KEY")
    kw = dict(typeCode="C", freqCode="A", clCode="HS", period=str(year), reporterCode=str(reporter),
              flowCode=flow, partnerCode=str(partner), partner2Code=None, customsCode=None, motCode=None,
              format_output="JSON", aggregateBy=None, breakdownMode="classic", countOnly=None, includeDesc=True)
    for attempt in range(3):
        try:
            if key:
                df = c.getFinalData(key, cmdCode="AG4", maxRecords=2500, **kw)
            else:
                df = c.previewFinalData(cmdCode="AG2", maxRecords=500, **kw)
            return df
        except Exception as e:
            print(f"  comtrade error ({e}); retry {attempt + 1}")
            time.sleep(3)
    return None


def _clean(df: pd.DataFrame | None, value_col: str) -> pd.DataFrame:
    if df is None or not len(df):
        return pd.DataFrame(columns=["cmdCode", "cmdDesc", value_col, "netWgt"])
    df = df[df.cmdCode.astype(str).str.fullmatch(r"\d{2}|\d{4}")].copy()
    df = df[(df.get("motCode", 0) == 0) & (df.get("customsCode", "C00") == "C00")] if "motCode" in df else df
    df = df.groupby(["cmdCode", "cmdDesc"], as_index=False).agg(v=("primaryValue", "sum"), netWgt=("netWgt", "sum"))
    return df.rename(columns={"v": value_col})


def build(years=(2024, 2023), c_rate: float = 0.07, min_flow: float = 1e6, sleep: float = 1.5) -> tuple[pd.DataFrame, dict]:
    rows, meta = [], {"annees_essayees": list(years), "c_cif_fob": c_rate, "seuil_usd": min_flow,
                      "mode": "getFinalData AG4" if os.environ.get("COMTRADE_KEY") else "previewFinalData AG2",
                      "paires": {}}
    for name, code in PARTNERS.items():
        for year in years:
            m = _clean(_fetch(TUNISIA, code, "M", year), "M_cif_usd")
            time.sleep(sleep)
            x = _clean(_fetch(code, TUNISIA, "X", year), "X_fob_usd")
            time.sleep(sleep)
            if len(m) and len(x):
                meta["paires"][name] = year
                j = m.merge(x.drop(columns="cmdDesc"), on="cmdCode", suffixes=("_m", "_x"))
                j["partner"], j["partner_fr"], j["year"] = name, PARTNERS_FR[name], year
                rows.append(j)
                print(f"  {name}: {year} ({len(j)} chapitres)")
                break
            print(f"  {name}: {year} indisponible (M={len(m)}, X={len(x)})")
    if not rows:
        return pd.DataFrame(), meta
    d = pd.concat(rows, ignore_index=True)
    d["M_fob_usd"] = d.M_cif_usd / (1 + c_rate)
    d = d[(d.M_fob_usd >= min_flow) & (d.X_fob_usd >= min_flow)].copy()  # drop small & one-sided flows
    d["gap_log"] = np.log(d.X_fob_usd / d.M_fob_usd)
    d["leak_usd"] = (d.X_fob_usd - d.M_fob_usd).clip(lower=0)
    d["ref_uv_kg"] = np.where(d.netWgt_x > 0, d.X_fob_usd / d.netWgt_x.replace(0, np.nan), np.nan)
    d["hs2"] = d.cmdCode.str[:2]
    return d.reset_index(drop=True), meta
