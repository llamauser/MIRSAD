"""Risk-cycle experiments: 3 simulated fraud schemes x ablations along the loop x 10 seeds (r = demo budget).

Ablations: random, rules, mirsad (④ alone), cycle_A1 (+② company score), cycle_A2 (+③ segments, Thompson,
audits), cycle_A3 (+⑦ trend alerts). Also: trend-detector lead time per scheme and false alarms on the
scheme-free data, and the demo run (cycle_A3, front scheme, seed 0) written to the risk register.
Outputs: results/cycle/*.  All numbers are on synthetic data.
"""
import json
import pickle
import sys
import time

import _bootstrap  # noqa: F401
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import ttest_ind

from mirsad.adapter import load
from mirsad.config import load_config, p
from mirsad.drift import inject
from mirsad.features import build_static
from mirsad.simulate import run, summarize
from mirsad.trends import scan

cfg = load_config()
sc = cfg["simulation"]
W0, R, DEMO_WEEK = cfg["drift"]["start_week"], sc["demo_r"], 40
OUT = p("results/cycle")
OUT.mkdir(parents=True, exist_ok=True)
SCENARIOS = ["front", "turncoat", "network"]
POLICIES = ["random", "rules", "mirsad", "cycle_A1", "cycle_A2", "cycle_A3"]
seeds = sc["seeds"]

# ---- scenario data (static features are label-free and past-only) + trend alerts ----
df = load(cfg)
statics, alerts, logs = {}, {}, {}
for s in SCENARIOS:
    f = p(f"data/processed/static_{s}.parquet") if s != "front" else p("data/processed/static_drift.parquet")
    dd, log = inject(df, cfg, scenario=s)
    logs[s] = log
    if not f.exists():
        t = time.time()
        st = build_static(dd, cfg["features"]["min_group_n"], verbose=False)
        st.to_parquet(f)
        print(f"static {s}: {time.time() - t:.0f}s")
    statics[s] = pd.read_parquet(f)
    alerts[s] = scan(statics[s], cfg)
    alerts[s].to_parquet(OUT / f"alerts_{s}.parquet")
base = pd.read_parquet(p("data/processed/static_base.parquet"))
alerts_base = scan(base, cfg)
json.dump(logs, open(OUT / "scenarios.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)


def detector_eval(s):
    """Lead time: first alert on/after W0 whose key matches the scheme's rows; alerts not matching = noise."""
    st, al = statics[s], alerts[s]
    inj = st[st.scheme == "injected"]
    keys = {"hs2": set(inj.hs2), "hs4": set(inj.hs4), "declarant": set(inj.declarant)}
    match = al.apply(lambda r: r.week >= W0 and r.cle in keys.get(r.cle_type, set()), axis=1) if len(al) else []
    hits = al[match] if len(al) else al
    return {"scenario": s, "n_alerts": int(len(al)), "n_alerts_before_scheme": int((al.week < W0).sum()) if len(al) else 0,
            "first_matching_alert_week": int(hits.week.min()) if len(hits) else None,
            "lead_time_weeks": int(hits.week.min() - W0) if len(hits) else None,
            "signals_matching": sorted(set(hits.signal)) if len(hits) else [],
            "alerts_after_w0_not_matching": int(((al.week >= W0) & ~np.asarray(match, bool)).sum()) if len(al) else 0}


det = [detector_eval(s) for s in SCENARIOS]
det.append({"scenario": "aucun schéma (données de base)", "n_alerts": int(len(alerts_base)),
            "false_alarms_per_year": int(len(alerts_base))})
json.dump(det, open(OUT / "detector.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("detector:", det)

# ---- grid ----
jobs = [(s, pol, seed) for s in SCENARIOS for pol in POLICIES for seed in seeds]
if "--demo-only" not in sys.argv:
    print(f"{len(jobs)} runs")
    t = time.time()
    res = Parallel(n_jobs=-2, verbose=2)(
        delayed(run)(statics[s], cfg, pol, R, 0.0, seed, alerts=alerts[s]) for s, pol, seed in jobs)
    weekly = pd.concat([w.assign(scenario=s) for (s, _, _), (w, _, _) in zip(jobs, res)], ignore_index=True)
    weekly.to_parquet(OUT / "cycle_runs.parquet")
    runtime = time.time() - t
    summ = pd.DataFrame([{"scenario": s, "policy": pol, "seed": seed, **summarize(g, W0)}
                         for (s, pol, seed), g in weekly.groupby(["scenario", "policy", "seed"])])
    summ.to_csv(OUT / "cycle_summary_by_seed.csv", index=False)
    metrics = ["revenue_at_k", "revenue_hist_at_k", "injected_recall_rev", "false_green_rev", "precision_at_k",
               "weeks_to_5_scheme_catches", "weeks_to_50pct_weekly_scheme_capture", "brier"]
    agg = summ.groupby(["scenario", "policy"])[metrics].agg(["mean", "std"]).round(4)
    agg.to_csv(OUT / "cycle_summary.csv")
    # Welch tests along the loop (each stage vs the previous one) and full loop vs baselines
    comps = [("cycle_A1", "mirsad"), ("cycle_A2", "cycle_A1"), ("cycle_A3", "cycle_A2"), ("cycle_A3", "mirsad"),
             ("cycle_A3", "rules"), ("cycle_A3", "random")]
    tests = []
    for s in SCENARIOS:
        for a, b in comps:
            for m in ["revenue_at_k", "revenue_hist_at_k", "injected_recall_rev"]:
                x = summ[(summ.scenario == s) & (summ.policy == a)][m]
                y = summ[(summ.scenario == s) & (summ.policy == b)][m]
                tt = ttest_ind(x, y, equal_var=False)
                tests.append({"scenario": s, "a": a, "b": b, "metric": m, "mean_a": round(x.mean(), 4),
                              "mean_b": round(y.mean(), 4), "diff": round(x.mean() - y.mean(), 4),
                              "p_value": round(float(tt.pvalue), 4), "worst_seed_a": round(x.min(), 4),
                              "worst_seed_b": round(y.min(), 4)})
    json.dump(tests, open(OUT / "ablation_tests.json", "w", encoding="utf-8"), indent=1)
    seg_cols = [c for c in summ.columns if c.startswith(("fraud_rate_", "volume_share_", "false_green_Confiance"))]
    seg = summ[summ.policy.isin(["cycle_A2", "cycle_A3"])].groupby(["scenario", "policy"])[seg_cols].mean().round(4)
    seg.to_csv(OUT / "segments.csv")
    json.dump({"runtime_s": round(runtime), "n_runs": len(jobs), "r": R, "seeds": seeds, "w0": W0},
              open(OUT / "meta.json", "w"), indent=1)
    print(agg.xs("revenue_at_k", axis=1, level=0).to_string())
    print(pd.DataFrame(tests).query("metric != 'revenue_hist_at_k'").to_string())

# ---- demo run: full loop on the front scheme, written to the risk register ----
w, keep, _ = run(statics["front"], cfg, "cycle_A3", R, 0.0, 0, keep_week=DEMO_WEEK, end_week=DEMO_WEEK,
                 alerts=alerts["front"], keep_all=True)
keep["register"].to_parquet(p("data/processed/risk_register.parquet"))
keep["companies"].to_parquet(p("data/processed/company_scores.parquet"))
alerts["front"].to_parquet(p("data/processed/trend_alerts.parquet"))
keep["batch"].to_parquet(p("results/demo_week.parquet"))
keep["revealed"].to_parquet(p("results/demo_revealed.parquet"))
pickle.dump(keep["model"], open(p("results/demo_model.pkl"), "wb"))
print("demo register:", keep["register"].shape, "| demo week lanes:", keep["batch"].lane.value_counts().to_dict(),
      "| segments:", keep["batch"].segment.value_counts().to_dict())
