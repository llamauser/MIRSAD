"""Export the results table (markdown) and key figures used in README / pitch, from the simulation outputs."""
import json

import _bootstrap  # noqa: F401
import pandas as pd

from mirsad.config import p

s = pd.read_csv(p("results/summary_by_seed.csv"))
g = s.groupby(["policy", "eps", "r"]).agg(["mean", "std"])


def f(pol, eps, r, m):
    return f"{g.loc[(pol, eps, r), (m, 'mean')] * 100:.1f} % ± {g.loc[(pol, eps, r), (m, 'std')] * 100:.1f}"


from mirsad.charts import series_label  # noqa: E402

SERIES = [("random", 0.0), ("rules", 0.0), ("model_p", 0.0), ("mirsad", 0.0), ("mirsad", 0.1), ("mirsad", 0.2)]
lines = ["| Politique | r | Revenu@k (total) | Revenu@k (fraudes historiques) | Schéma injecté capturé (revenu) "
         "| Faux-vert (revenu) |", "|---|---|---|---|---|---|"]
for r in sorted(s.r.unique()):
    for pol, eps in SERIES:
        name = series_label(pol, eps)
        lines.append(f"| {name} | {r:.0%} | {f(pol, eps, r, 'revenue_at_k')} | {f(pol, eps, r, 'revenue_hist_at_k')} "
                     f"| {f(pol, eps, r, 'injected_recall_rev')} | {f(pol, eps, r, 'false_green_rev')} |")
p("results/results_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

key = {}
for r in sorted(s.r.unique()):
    for pol, eps in SERIES:
        for m in ["revenue_at_k", "revenue_hist_at_k", "injected_recall_rev", "false_green_rev", "precision_at_k"]:
            key[f"{pol}|eps={eps:g}|r={r:g}|{m}"] = [round(g.loc[(pol, eps, r), (m, "mean")], 4),
                                                   round(g.loc[(pol, eps, r), (m, "std")], 4)]
json.dump(key, open(p("results/key_figures.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("\n".join(lines))

# ---- exploration vs no exploration: Welch t-test over seeds + worst seed (honest significance check) ----
from scipy.stats import ttest_ind  # noqa: E402

stats = []
for r in sorted(s.r.unique()):
    base = s[(s.policy == "mirsad") & (s.eps == 0.0) & (s.r == r)]
    for eps in [0.1, 0.2]:
        alt = s[(s.policy == "mirsad") & (s.eps == eps) & (s.r == r)]
        for m in ["revenue_at_k", "revenue_hist_at_k", "injected_recall_rev"]:
            t, pv = ttest_ind(alt[m], base[m], equal_var=False)
            stats.append({"r": r, "eps": eps, "metric": m, "mean_eps0": round(base[m].mean(), 4),
                          "mean_eps": round(alt[m].mean(), 4), "diff": round(alt[m].mean() - base[m].mean(), 4),
                          "p_value_welch": round(float(pv), 3), "min_seed_eps0": round(base[m].min(), 4),
                          "min_seed_eps": round(alt[m].min(), 4), "n_seeds": int(len(base))})
json.dump(stats, open(p("results/exploration_stats.json"), "w", encoding="utf-8"), indent=1)
print("\nexploration vs eps=0 (Welch):")
for x in stats:
    if x["metric"] != "revenue_hist_at_k":
        print(f"  r={x['r']:.2f} eps={x['eps']} {x['metric']:<20} diff={x['diff']:+.3f} p={x['p_value_welch']:.3f} "
              f"worst seed {x['min_seed_eps0']:.3f} -> {x['min_seed_eps']:.3f}")
