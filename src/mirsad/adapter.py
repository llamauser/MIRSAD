"""Load any declaration CSV and map it to the MIRSAD canonical schema."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import load_config, p

CANONICAL = ["id", "date", "importer", "declarant", "country", "office", "hs10",
             "quantity", "weight", "fob", "cif", "taxes", "label_fraud", "label_revenue"]
REQUIRED = ["id", "date", "importer", "hs10", "cif"]
NUMERIC = ["quantity", "weight", "fob", "cif", "taxes", "label_fraud", "label_revenue"]

# module/tool -> canonical columns it needs
MODULE_NEEDS = {
    "features.unit_value (uv)": ["cif", "quantity"],
    "features.unit_value_kg (uv_kg)": ["cif", "weight"],
    "features.tax_rate": ["taxes", "cif"],
    "features.fob_cif": ["fob", "cif"],
    "features.risk_profiles (supervised)": ["label_fraud"],
    "model.classifier P(fraude)": ["label_fraud"],
    "model.revenue R_hat": ["label_revenue"],
    "graph (importer-declarant)": ["importer", "declarant"],
    "tool.get_peer_prices": ["cif", "quantity", "country"],
    "tool.get_entity_history": ["importer"],
    "policy.rules": ["taxes", "cif"],
}


def normalize_hs(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.replace(r"\D", "", regex=True)
    return s.str.zfill(10).str[:10]


def load(config: dict | None = None, path: str | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    src = path or p(cfg["paths"]["raw_csv"])
    raw = pd.read_csv(src, dtype=str)
    mapping = {k: v for k, v in cfg["columns"].items() if v and v in raw.columns}
    df = pd.DataFrame({k: raw[v] for k, v in mapping.items()})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"required canonical columns missing: {missing}")
    df["date"] = pd.to_datetime(df["date"], format=cfg.get("date_format"), errors="coerce")
    for c in NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["hs10"] = normalize_hs(df["hs10"])
    df["hs6"], df["hs4"], df["hs2"] = df.hs10.str[:6], df.hs10.str[:4], df.hs10.str[:2]
    for c in ["importer", "declarant", "country", "office", "id"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    df = df.dropna(subset=["date"]).sort_values(["date", "id"]).reset_index(drop=True)
    df["week"] = ((df.date - df.date.min()).dt.days // 7 + 1).astype(int)
    return df


def schema_report(df: pd.DataFrame, verbose: bool = True) -> dict:
    present = [c for c in CANONICAL if c in df.columns]
    report = {"n_rows": len(df), "present": present,
              "absent": [c for c in CANONICAL if c not in df.columns], "modules": {}}
    for mod, needs in MODULE_NEEDS.items():
        report["modules"][mod] = all(c in df.columns for c in needs)
    if "label_fraud" not in df.columns:
        report["mode"] = "unsupervised (rules + IsolationForest only)"
    else:
        report["mode"] = "supervised"
    if verbose:
        print(f"rows={report['n_rows']}  mode={report['mode']}")
        print("present:", present)
        print("absent :", report["absent"])
        for mod, ok in report["modules"].items():
            print(f"  [{'OK' if ok else '--'}] {mod}")
    return report
