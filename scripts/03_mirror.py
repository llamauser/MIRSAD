"""Build the mirror dataset (UN Comtrade) -> data/processed/mirror.parquet. Never fabricates data."""
import json

import _bootstrap  # noqa: F401

from mirsad.config import load_config, p
from mirsad.mirror import build

cfg = load_config()["mirror"]
out = p("data/processed/mirror.parquet")
try:
    df, meta = build(c_rate=cfg["cif_fob_c"], min_flow=cfg["min_flow_usd"])
except Exception as e:
    df, meta = None, {"erreur": str(e)}
if df is None or not len(df):
    meta["statut"] = "données miroir indisponibles"
    print("!! données miroir indisponibles — the app will say so; nothing fabricated.")
else:
    df.to_parquet(out)
    meta |= {"statut": "ok", "n_lignes": len(df), "fuite_totale_usd": float(df.leak_usd.sum())}
    print(df.sort_values("leak_usd", ascending=False).head(10)[
        ["partner", "year", "cmdCode", "cmdDesc", "M_fob_usd", "X_fob_usd", "gap_log", "leak_usd"]].to_string())
json.dump(meta, open(p("results/mirror_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(meta)
