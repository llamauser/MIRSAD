"""Run the policy x budget x epsilon x seed grid on the drifted dataset.

Outputs: results/sim_runs.parquet, results/metrics.json, results/charts/*.png,
demo artefacts (results/demo_*.parquet, results/demo_model.pkl)."""
import json
import pickle
import sys
import time

import _bootstrap  # noqa: F401
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

from mirsad.charts import EPS_COLORS, INK, INK2, POLICY_COLORS, POLICY_LABELS, style_axes  # noqa: E402
from mirsad.config import load_config, p  # noqa: E402
from mirsad.simulate import run, summarize  # noqa: E402

cfg = load_config()
sc = cfg["simulation"]
W0 = cfg["drift"]["start_week"]
DEMO_WEEK = 40
static = pd.read_parquet(p("data/processed/static_drift.parquet"))

jobs = []
for r in sc["r_grid"]:
    for seed in sc["seeds"]:
        for pol in sc["policies"]:
            if pol == "mirsad":
                jobs += [(pol, r, e, seed) for e in sc["eps_grid"] if e > 0]  # eps=0 == model_er
            else:
                jobs.append((pol, r, 0.0, seed))
print(f"{len(jobs)} runs")
t = time.time()
if "--charts-only" in sys.argv:
    weekly = pd.read_parquet(p("results/sim_runs.parquet"))
    runtime = json.load(open(p("results/metrics.json"), encoding="utf-8"))["grid_runtime_s"]
else:
    res = Parallel(n_jobs=-2, verbose=5)(delayed(run)(static, cfg, *j) for j in jobs)
    weekly = pd.concat([w for w, _, _ in res], ignore_index=True)
    weekly.to_parquet(p("results/sim_runs.parquet"))
    runtime = time.time() - t
print(f"grid done in {runtime:.0f}s")

# ---- metrics: mean +- std over seeds --------------------------------------
summ = []
for (pol, r, eps, seed), g in weekly.groupby(["policy", "r", "eps", "seed"]):
    summ.append({"policy": pol, "r": r, "eps": eps, "seed": seed, **summarize(g, W0)})
summ = pd.DataFrame(summ)
summ.to_csv(p("results/summary_by_seed.csv"), index=False)
agg = summ.drop(columns="seed").groupby(["policy", "r", "eps"]).agg(["mean", "std"])
metrics = {"dataset": "BACUDA synthetic declarations + injected scheme (simulated)",
           "grid_runtime_s": round(runtime), "n_runs": len(jobs), "seeds": sc["seeds"],
           "retrain_every_weeks": sc.get("retrain_every", 1), "weeks": [sc["start_week"], sc["end_week"]],
           "drift": json.load(open(p("results/drift_log.json"), encoding="utf-8")), "runs": []}
for (pol, r, eps), row in agg.iterrows():
    d = {"policy": pol, "r": r, "eps": eps}
    for m in summ.columns.drop(["policy", "r", "eps", "seed"]):
        d[m] = {"mean": round(float(row[(m, "mean")]), 4), "std": round(float(row[(m, "std")]), 4)}
    metrics["runs"].append(d)
json.dump(metrics, open(p("results/metrics.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

# ---- Chart A: Revenue@k vs r per policy (eps=default for mirsad) ------------
mean = summ.groupby(["policy", "r", "eps"]).revenue_at_k.mean().reset_index()
chart_a = mean[(mean.policy != "mirsad") | (mean.eps == sc["default_eps"])]
chart_a.to_csv(p("results/chart_a.csv"), index=False)
fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
for pol in ["random", "rules", "model_p", "model_er", "mirsad"]:
    d = chart_a[chart_a.policy == pol].sort_values("r")
    ax.plot(d.r * 100, d.revenue_at_k * 100, color=POLICY_COLORS[pol], lw=2, marker="o", ms=5,
            label=POLICY_LABELS[pol])
style_axes(ax)
ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
ax.set_xlabel("Budget d'inspection r (% des déclarations / semaine)", color=INK2)
ax.set_ylabel("Revenu@k (% du revenu récupérable)", color=INK2)
ax.set_title("A — Part du revenu récupérable capturée, à budget égal\n(données synthétiques, moyenne sur "
             f"{len(sc['seeds'])} graines)", loc="left", fontsize=10, color=INK)
ax.set_xlim(0, 21)
fig.tight_layout()
fig.savefig(p("results/charts/chart_a_revenue_vs_budget.png"))

# ---- Chart B: cumulative injected revenue caught after W0, by eps (r=demo) --
r0 = sc["demo_r"]
b = weekly[(weekly.r == r0) & (weekly.week >= W0) &
           (((weekly.policy == "model_er")) | (weekly.policy == "mirsad"))].copy()
b = b.sort_values("week")
b["cum"] = b.groupby(["policy", "eps", "seed"]).rev_inj_sel.cumsum()
tot = weekly[(weekly.r == r0) & (weekly.week >= W0) & (weekly.policy == "random") & (weekly.seed == 0)]
cum_total = tot.sort_values("week").rev_inj_total.cumsum().values
chart_b = b.groupby(["eps", "week"]).cum.agg(["mean", "std"]).reset_index()
chart_b.to_csv(p("results/chart_b.csv"), index=False)
fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
weeks_b = sorted(b.week.unique())
ax.plot(weeks_b, cum_total / 1e6, color="#8a8984", lw=1.5, ls="--", label="Total du schéma injecté")
rb = weekly[(weekly.r == r0) & (weekly.week >= W0) & (weekly.policy == "rules")].sort_values("week").copy()
rb["cum"] = rb.groupby("seed").rev_inj_sel.cumsum()
rb = rb.groupby("week").cum.mean()
ax.plot(rb.index, rb.values / 1e6, color=POLICY_COLORS["rules"], lw=1.5, ls=":", label="Règles (référence)")
for eps in sorted(chart_b.eps.unique()):
    d = chart_b[chart_b.eps == eps]
    ax.fill_between(d.week, (d["mean"] - d["std"]) / 1e6, (d["mean"] + d["std"]) / 1e6,
                    color=EPS_COLORS[eps], alpha=0.10, lw=0)
    ax.plot(d.week, d["mean"] / 1e6, color=EPS_COLORS[eps], lw=2, label=f"MIRSAD ε = {eps:g}".replace(".", ","))
style_axes(ax)
ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
ax.set_xlabel("Semaine", color=INK2)
ax.set_ylabel("Revenu cumulé capturé (M TND simulés)", color=INK2)
ax.set_title(f"B — Schéma de fraude injecté (simulé) dès la semaine {W0}, r = {r0:.0%}\n"
             f"(moyenne ± écart-type sur {len(sc['seeds'])} graines)",
             loc="left", fontsize=10, color=INK)
ax.set_xlim(W0 - 0.5, 52.5)
fig.tight_layout()
fig.savefig(p("results/charts/chart_b_injected_scheme.png"))

# ---- demo artefacts: MIRSAD r=demo_r, eps=default, seed 0, demo week --------
_, keep, _ = run(static, cfg, "mirsad", r0, sc["default_eps"], 0, keep_week=DEMO_WEEK, end_week=DEMO_WEEK)
keep["batch"].to_parquet(p("results/demo_week.parquet"))
keep["revealed"].to_parquet(p("results/demo_revealed.parquet"))
pickle.dump(keep["model"], open(p("results/demo_model.pkl"), "wb"))
print("demo week", DEMO_WEEK, keep["batch"].lane.value_counts().to_dict())

view = summ[summ.r == r0].groupby(["policy", "eps"]).mean(numeric_only=True).drop(columns=["r", "seed"])
print(view.round(3).to_string())
