"""Leakage, time order and budget tests for the selective-label simulator."""
import numpy as np
import pandas as pd

from mirsad.features import build_static
from mirsad.simulate import run


def test_no_label_leakage(static, cfg):
    """Each week, the training rows are exactly the rows revealed in *previous* weeks."""
    _, _, audits = run(static, cfg, "mirsad", 0.05, 0.0, seed=0, audit=True, end_week=8)
    revealed, trained = set(), 0
    for a in sorted(audits, key=lambda a: (a["week"], a["event"] == "reveal")):
        if a["event"] == "train":
            assert a["ids"] <= revealed, "training on rows never inspected"
            assert a["ids"] == revealed, "revealed rows missing from training"
            assert a["train_max_week"] < a["week"], "training on the current or a future week"
            trained += 1
        else:
            revealed |= a["ids"]
    assert trained >= 5
    assert len(revealed) < 0.15 * (static.week <= 8).sum()  # ~10% warm start + 5% per week


def test_future_labels_do_not_change_the_past(static, cfg):
    """Flipping all labels from week W onwards leaves every decision up to week W unchanged."""
    W = 7
    alt = static.copy()
    fut = alt.week >= W
    alt.loc[fut, "label_fraud"] = 1 - alt.loc[fut, "label_fraud"]
    alt.loc[fut, "label_revenue"] = alt.loc[fut, "label_revenue"] + 1000
    a, ka, _ = run(static, cfg, "mirsad", 0.05, 0.1, seed=1, keep_week=W, end_week=W)
    b, kb, _ = run(alt, cfg, "mirsad", 0.05, 0.1, seed=1, keep_week=W, end_week=W)
    cols = ["week", "k", "n_new_imp_sel"]
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True))
    np.testing.assert_allclose(ka["batch"].er.values, kb["batch"].er.values)
    assert (ka["batch"].lane.values == kb["batch"].lane.values).all()


def test_time_order_static_features(cfg):
    """Static features of week w are identical whether or not later weeks exist."""
    from mirsad.adapter import load
    df = load(cfg)
    df = df[df.week <= 6]
    full = build_static(df, verbose=False)
    trunc = build_static(df[df.week <= 4], verbose=False)
    cols = ["z_uv", "z_uv_kg", "z_tax_rt", "hist_count_importer", "days_since_first", "is_new_combo", "iso_score"]
    pd.testing.assert_frame_equal(full[full.week == 4][cols].sort_index(), trunc[trunc.week == 4][cols].sort_index())


def test_days_since_first_is_finite(static):
    v = static.days_since_first
    assert v.notna().all() and (v >= 0).all() and v.max() <= 366


def test_budget_respected(static, cfg):
    for pol, eps in [("random", 0.0), ("rules", 0.0), ("mirsad", 0.2)]:
        w, _, _ = run(static, cfg, pol, 0.05, eps, seed=0, end_week=6)
        assert (w.k == (0.05 * w.N).round().astype(int)).all()
