"""Smoke test of the precomputed demo path (< 2 min): required files, every app page, one fallback dossier."""
import sys
import time
import warnings

import _bootstrap  # noqa: F401

from mirsad.config import ROOT

warnings.filterwarnings("ignore")
t0 = time.time()
REQUIRED = [
    "data/processed/static_drift.parquet", "results/metrics.json", "results/summary_by_seed.csv",
    "results/sim_runs.parquet", "results/demo_week.parquet", "results/demo_revealed.parquet", "results/demo_model.pkl",
    "results/charts/chart_a_revenue_vs_budget.png", "results/charts/chart_b_injected_scheme.png",
    "results/dossiers/index.json", "results/espece_metrics.json", "results/espece_results.csv",
    "data/espece/demo_set.csv", "data/hs/harmonized-system.csv", "results/drift_log.json",
]
OPTIONAL = ["data/processed/mirror.parquet"]  # app shows « données miroir indisponibles » if absent
missing = [f for f in REQUIRED if not (ROOT / f).exists()]
for f in OPTIONAL:
    print(f"[{'OK' if (ROOT / f).exists() else 'ABSENT (optionnel)'}] {f}")
if missing:
    sys.exit(f"FAIL missing files: {missing}")
print(f"[OK] {len(REQUIRED)} required files")

sys.path.insert(0, str(ROOT / "app"))
from streamlit.testing.v1 import AppTest  # noqa: E402

pages = ["app/Accueil.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "app/pages").glob("*.py"))
bad = []
for pg in pages:
    at = AppTest.from_file(str(ROOT / pg), default_timeout=120).run()
    exc = [e.value for e in at.exception]
    print(f"[{'OK' if not exc else 'FAIL'}] {pg}")
    if exc:
        bad.append((pg, exc[:1]))

from mirsad.agent.loop import investigate  # noqa: E402
from mirsad.context import get_context  # noqa: E402

b = get_context().batch
cid = b[b.lane == "Rouge"].index[0]
res = investigate(cid, use_llm=False)
ok = res["validation"][-1]["erreurs"] == []
print(f"[{'OK' if ok else 'FAIL'}] fallback dossier {cid} validated")
dt = time.time() - t0
print(f"smoke test: {dt:.0f}s")
if bad or not ok or dt > 120:
    sys.exit(f"FAIL {bad}")
print("SMOKE TEST PASSED")
