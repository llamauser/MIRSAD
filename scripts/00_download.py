"""Download the BACUDA synthetic declarations CSV and verify the known facts."""
import subprocess
import sys
import urllib.request

import _bootstrap  # noqa: F401
import pandas as pd

from mirsad.adapter import load, schema_report
from mirsad.config import load_config, p

cfg = load_config()
dest = p(cfg["paths"]["raw_csv"])
dest.parent.mkdir(parents=True, exist_ok=True)
if not dest.exists():
    try:
        print("downloading", cfg["source_url"])
        urllib.request.urlretrieve(cfg["source_url"], dest)
    except Exception as e:  # fallback: shallow clone
        print("direct download failed:", e, "-> git clone")
        tmp = p("data/raw/_repo")
        subprocess.run(["git", "clone", "--depth", "1", cfg["source_repo"], str(tmp)], check=True)
        (tmp / "data" / "synthetic-imports-declarations.csv").replace(dest)

raw = pd.read_csv(dest, dtype=str)
df = load(cfg)
checks = {
    "rows == 100000": len(raw) == 100_000,
    "14 columns": raw.shape[1] == 14,
    "date range 2013-01-02..2013-12-31": (str(df.date.min().date()), str(df.date.max().date())) == ("2013-01-02", "2013-12-31"),
    "fraud rate ~7.58%": abs(df.label_fraud.mean() - 0.0758) < 0.001,
    "112 countries": df.country.nunique() == 112,
    "23 offices": df.office.nunique() == 23,
}
print("shape", raw.shape)
print(f"fraud rate={df.label_fraud.mean():.4f} importers={df.importer.nunique()} declarants={df.declarant.nunique()} "
      f"hs10={df.hs10.nunique()} weeks={df.week.min()}..{df.week.max()}")
for k, v in checks.items():
    print(f"  [{'OK' if v else 'FAIL'}] {k}")
schema_report(df)
if not all(checks.values()):
    sys.exit("DATASET CHECKS FAILED — stop and ask the user")
