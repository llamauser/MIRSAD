"""Contract B — the risk register: one table where every stage of the cycle writes its outputs.

Written by the simulator (demo run, full loop) week by week, as-of each week:
  ① anomaly signals (z_uv, z_uv_kg, z_tax_rt, z_kg_unit, iso_score)   ② ent_mean, ent_sd, ent_neff, ent_trend, link_risk
  ③ segment   ④ p, r_hat, er, lane, selected_by   ⑥ label_fraud / label_revenue (known only if inspected)
  ⑦ alert (row matches an active trend alert)
Companion tables: company_scores (② per company per week) and trend_alerts (⑦).
The app and the agent tools read these files only.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import p


@lru_cache(maxsize=1)
def register() -> pd.DataFrame:
    return pd.read_parquet(p("data/processed/risk_register.parquet"))


@lru_cache(maxsize=1)
def companies() -> pd.DataFrame:
    return pd.read_parquet(p("data/processed/company_scores.parquet"))


@lru_cache(maxsize=1)
def alerts() -> pd.DataFrame:
    f = p("data/processed/trend_alerts.parquet")
    return pd.read_parquet(f) if f.exists() else pd.DataFrame()


def company_history(importer: str) -> pd.DataFrame:
    c = companies()
    return c[c.importer == importer].sort_values("week")


def outcomes(importer: str, before_week: int) -> pd.DataFrame:
    """Inspection outcomes of a company known before `before_week` (inspected rows only)."""
    r = register()
    r = r[(r.importer == importer) & (r.week < before_week) & (r.lane == "Rouge")]
    return r[["id", "week", "hs6", "selected_by", "label_fraud", "label_revenue"]]
