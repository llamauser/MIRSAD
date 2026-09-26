"""POST-HOC variant, run after seeing the pre-registered cycle results (turncoat scheme degraded):
cycle_A3b = full cycle, but « Confiance » companies remain eligible for exploitation. Reported separately."""
import json

import _bootstrap  # noqa: F401
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import ttest_ind

from mirsad.config import load_config, p
from mirsad.simulate import run, summarize

cfg = load_config()
W0, R, seeds = cfg["drift"]["start_week"], cfg["simulation"]["demo_r"], cfg["simulation"]["seeds"]
files = {"front": "static_drift", "turncoat": "static_turncoat", "network": "static_network"}
statics = {s: pd.read_parquet(p(f"data/processed/{f}.parquet")) for s, f in files.items()}
alerts = {s: pd.read_parquet(p(f"results/cycle/alerts_{s}.parquet")) for s in files}
jobs = [(s, seed) for s in files for seed in seeds]
res = Parallel(n_jobs=-2)(delayed(run)(statics[s], cfg, "cycle_A3b", R, 0.0, seed, alerts=alerts[s]) for s, seed in jobs)
summ = pd.DataFrame([{"scenario": s, "policy": "cycle_A3b", "seed": seed, **summarize(w, W0)}
                     for (s, seed), (w, _, _) in zip(jobs, res)])
pre = pd.read_csv(p("results/cycle/cycle_summary_by_seed.csv"))
summ.to_csv(p("results/cycle/posthoc_A3b_by_seed.csv"), index=False)
out = []
for s in files:
    for ref in ["cycle_A3", "mirsad", "rules"]:
        for m in ["revenue_at_k", "injected_recall_rev", "revenue_hist_at_k"]:
            x, y = summ[summ.scenario == s][m], pre[(pre.scenario == s) & (pre.policy == ref)][m]
            out.append({"scenario": s, "a": "cycle_A3b", "b": ref, "metric": m, "mean_a": round(x.mean(), 4),
                        "sd_a": round(x.std(), 4), "mean_b": round(y.mean(), 4), "diff": round(x.mean() - y.mean(), 4),
                        "p_value": round(float(ttest_ind(x, y, equal_var=False).pvalue), 4)})
json.dump(out, open(p("results/cycle/posthoc_A3b_tests.json"), "w"), indent=1)
print(pd.DataFrame(out).query("metric != 'revenue_hist_at_k'").to_string())
