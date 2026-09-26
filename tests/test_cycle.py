"""As-of contract for the whole risk cycle (②③④⑦): no stage may use future information or unrevealed labels."""
import numpy as np
import pandas as pd

from mirsad.entity import company_table, posterior, segment
from mirsad.simulate import run
from mirsad.trends import scan


def test_full_cycle_no_label_leakage(static, cfg):
    al = scan(static[static.week <= 8], cfg)
    _, _, audits = run(static, cfg, "cycle_A3", 0.05, 0.0, seed=0, audit=True, end_week=8, alerts=al)
    revealed = set()
    for a in sorted(audits, key=lambda a: (a["week"], a["event"] == "reveal")):
        if a["event"] == "train":
            assert a["ids"] == revealed and a["train_max_week"] < a["week"]
        else:
            revealed |= a["ids"]


def test_company_score_ignores_current_and_future_outcomes(static):
    rev = static[static.week <= 10].sample(500, random_state=0).assign(rev_src="warm")
    before = posterior(rev, "importer", 6, p0=0.08)
    flipped = rev.copy()
    flipped.loc[flipped.week >= 6, "label_fraud"] = 1 - flipped.loc[flipped.week >= 6, "label_fraud"]
    after = posterior(flipped, "importer", 6, p0=0.08)
    pd.testing.assert_frame_equal(before.sort_index(), after.sort_index())


def test_segments_rules():
    seg = segment([0.05, 0.30, 0.02, 0.12], [0.5, 5, 5, 5], p0=0.08)
    assert list(seg) == ["Surveillé", "Critique", "Confiance", "Standard"]


def test_trend_alerts_are_as_of(static, cfg):
    full = scan(static[static.week <= 30], cfg)
    trunc = scan(static[static.week <= 27], cfg)
    a = full[full.week <= 27].sort_values(["week", "alert_id"]).reset_index(drop=True)
    b = trunc.sort_values(["week", "alert_id"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a[["alert_id", "valeur", "z"]], b[["alert_id", "valeur", "z"]])


def test_company_table_uncertainty_shrinks_with_inspections(static, cfg):
    rev = static[static.week < 20].assign(rev_src="warm")  # pretend everything was inspected
    t = company_table(rev, static[static.week < 20], 20, cfg)
    p0, alpha = t.attrs["p0"], cfg["entity"]["alpha"]
    prior_sd = np.sqrt(p0 * (1 - p0) / (alpha + 1))
    many = t[t.ent_neff >= 5].ent_sd.median()
    assert np.isfinite(many) and many < prior_sd
