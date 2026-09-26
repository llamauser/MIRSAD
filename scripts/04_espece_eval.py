"""Evaluate the espèce check on the team-built demo set -> results/espece_metrics.json."""
import json
import sys

import _bootstrap  # noqa: F401
import pandas as pd

from mirsad.config import p
from mirsad.espece import classify

use_llm = "--no-llm" not in sys.argv
df = pd.read_csv(p("data/espece/demo_set.csv"), dtype={"gold_hs6": str, "declared_hs6": str})
rows = []
for r in df.itertuples():
    res = classify(r.description, r.declared_hs6, r.cif, use_llm=use_llm)
    codes = [t["code"] for t in res["top3"]]
    rows.append({"id": r.id, "description": r.description, "gold": r.gold_hs6, "declare": r.declared_hs6,
                 "misdeclared": r.misdeclared, "injection": r.injection, "mode": res["mode"],
                 "top1": codes[0], "top3": " ".join(codes), "conf1": res["top3"][0]["confidence"],
                 "top1_hs6": codes[0] == r.gold_hs6, "top3_hs6": r.gold_hs6 in codes,
                 "top1_hs4": codes[0][:4] == r.gold_hs6[:4], "top3_hs4": r.gold_hs6[:4] in [c[:4] for c in codes],
                 "alerte": res["alerte_espece"], "ecart_droits_TND": res["ecart_droits_TND"],
                 "injection_detectee": res["injection_flag"]})
out = pd.DataFrame(rows)
out.to_csv(p("results/espece_results.csv"), index=False)
tp = int((out.alerte & (out.misdeclared == 1)).sum())
fp = int((out.alerte & (out.misdeclared == 0)).sum())
fn = int((~out.alerte & (out.misdeclared == 1)).sum())
m = {
    "jeu": "jeu de démonstration construit par l'équipe (50 descriptions) — évaluation optimiste : le glossaire FR→EN "
           "et les descriptions ont été rédigés par la même équipe",
    "mode": out["mode"].mode()[0], "n": len(out),
    "top1_hs6": round(out.top1_hs6.mean(), 3), "top3_hs6": round(out.top3_hs6.mean(), 3),
    "top1_hs4": round(out.top1_hs4.mean(), 3), "top3_hs4": round(out.top3_hs4.mean(), 3),
    "alerte_precision": round(tp / (tp + fp), 3) if tp + fp else None,
    "alerte_rappel": round(tp / (tp + fn), 3) if tp + fn else None,
    "tp": tp, "fp": fp, "fn": fn,
    "injections_detectees": f"{int(out.injection_detectee.sum())}/{int(out.injection.sum())}",
    "faux_positifs_injection": int((out.injection_detectee.astype(bool) & (out.injection == 0)).sum()),
    "ecart_droits_total_TND_illustratif": float(out.ecart_droits_TND.sum()),
}
m["modes_par_ligne"] = out["mode"].value_counts().to_dict()
json.dump(m, open(p("results/espece_metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
tag = "bm25" if m["mode"] == "bm25" else ("local" if "local" in m["mode"] else "openai")
json.dump(m, open(p(f"results/espece_metrics_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
out.to_csv(p(f"results/espece_results_{tag}.csv"), index=False)
print(json.dumps(m, ensure_ascii=False, indent=1))
print(out[~out.top3_hs6][["id", "gold", "top3", "description"]].to_string())
