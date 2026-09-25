"""Build static (label-free, past-only) features for the base and drifted datasets,
then a quick sanity run of the model on a simple time split (NOT the headline eval)."""
import json
import time

import _bootstrap  # noqa: F401
import pandas as pd

from mirsad.adapter import load
from mirsad.config import load_config, p
from mirsad.drift import inject
from mirsad.features import build_static, risk_profiles
from mirsad.model import RiskModel, eval_scores

cfg = load_config()
out = p(cfg["paths"]["processed"])
df = load(cfg)

t = time.time()
if (out / "static_base.parquet").exists():
    base = pd.read_parquet(out / "static_base.parquet")
else:
    base = build_static(df, cfg["features"]["min_group_n"])
    base["scheme"] = "none"
    base.to_parquet(out / "static_base.parquet")
print(f"base static features: {base.shape} in {time.time()-t:.0f}s")

t = time.time()
dd, log = inject(df, cfg)
drift = build_static(dd, cfg["features"]["min_group_n"])
drift.to_parquet(out / "static_drift.parquet")
json.dump(log, open(p("results/drift_log.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"drift static features: {drift.shape} in {time.time()-t:.0f}s; drift log: {log}")

# --- sanity check: train Jan-Feb (all labels), test March ------------------
tr = base[base.date.dt.month <= 2].copy()
te = base[base.date.dt.month == 3].copy()
tr = tr.join(risk_profiles(tr.iloc[0:0], tr, cfg["features"]["alpha"], p0=0.0758))  # no leakage: prior only in train
te = te.join(risk_profiles(tr, te, cfg["features"]["alpha"]))
m = RiskModel(**{k: cfg["model"][k] for k in ["n_estimators", "learning_rate", "num_leaves", "seed"]})
m.fit(tr, calib_week=int(tr.week.max()))
s = m.score(te)
res = eval_scores(te.label_fraud.values, te.label_revenue.values, s.p.values, s.er.values)
res["n_train"], res["n_test"] = len(tr), len(te)
res["note"] = "Sanity split only (train Jan-Feb all labels, test March). Not the headline evaluation."
json.dump(res, open(p("results/sanity_split.json"), "w"), indent=2)
print("SANITY", res)
