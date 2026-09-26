"""⑥ APPRENDRE — leakage-safe weekly simulation with selective labels (the closed loop).

Each week (as-of contract): features from the past -> train on inspected rows only -> score the week
-> select under budget -> reveal labels of the selected rows only -> next week.

Policies
  random, rules, model_p, mirsad (ER ranking, eps exploration)          -- historical baselines
  cycle_A1  mirsad + ② company score features (Beta posterior, decay, uncertainty, links)
  cycle_A2  A1 + ③ segment budgets: exploit Critique/Standard/Surveillé by ER, Thompson sampling on
            Surveillé, random audits on Confiance
  cycle_A3  A2 + ⑦ trend alerts: more exploration budget, steered to the flagged segment
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .entity import ENTITY_FEATURES, batch_features, company_table
from .features import MODEL_FEATURES, risk_profiles
from .model import RiskModel
from .policy import LANE_ORANGE, LANE_ROUGE, LANE_VERT, NEEDS_MODEL, assign_lanes, select
from .trends import active_mask

CYCLE = {"cycle_A1": dict(entity=True), "cycle_A2": dict(entity=True, segments=True),
         "cycle_A3": dict(entity=True, segments=True, trends=True),
         # POST-HOC variant (designed after seeing the turncoat result): trusted companies stay eligible for
         # exploitation, so a « Confiance » company whose declaration has a high expected amount is still inspected
         "cycle_A3b": dict(entity=True, segments=True, trends=True, trust_exploit=True)}
REGISTER_COLS = ["id", "week", "importer", "declarant", "country", "office", "hs6", "cif", "taxes",
                 "z_uv", "z_uv_kg", "z_tax_rt", "z_kg_unit", "iso_score", "is_new_importer",
                 "ent_mean", "ent_sd", "ent_neff", "ent_trend", "link_risk", "segment",
                 "p", "r_hat", "er", "lane", "selected_by", "alert", "label_fraud", "label_revenue", "scheme"]


def _cycle_select(b, k, rng, cc, alert_rows, trust_exploit=False):
    """③+④ budget split by segment. Returns positions, ranking score, source label per selected position."""
    seg, er = b.segment.values, b.er.values
    n = len(b)
    k_audit = max(1, int(round(cc["audit_share"] * k)))
    share = cc["explore_share_alert"] if alert_rows.any() else cc["explore_share"]
    k_explore = int(round(share * k))
    k_exploit = max(0, k - k_audit - k_explore)
    taken = np.zeros(n, bool)
    src = {}
    # exploitation: ER ranking outside « Confiance » (facilitation of compliant operators)
    pool = np.arange(n) if trust_exploit else np.where(seg != "Confiance")[0]
    ex = pool[np.argsort(-er[pool], kind="stable")[:k_exploit]]
    taken[ex] = True
    src.update({i: "exploitation" for i in ex})
    # exploration: Thompson sampling on « Surveillé » (+ rows matching an active trend alert)
    pool = np.where(((seg == "Surveillé") | alert_rows) & ~taken)[0]
    if len(pool) and k_explore:
        conc = cc["kappa"] + b.ent_neff.values[pool]
        p = np.clip(b.p.values[pool], 1e-3, 1 - 1e-3)
        theta = rng.beta(p * conc, (1 - p) * conc)
        score = theta * np.maximum(b.r_hat.values[pool], 1.0) * np.where(alert_rows[pool], 3.0, 1.0)
        pick = pool[np.argsort(-score)[:k_explore]]
        taken[pick] = True
        src.update({i: "exploration" for i in pick})
    # random audits on « Confiance » (unbiased false-green and base-rate measurement)
    pool = np.where((seg == "Confiance") & ~taken)[0]
    if len(pool):
        pick = rng.choice(pool, size=min(k_audit, len(pool)), replace=False)
        taken[pick] = True
        src.update({i: "audit" for i in pick})
    # top up to exactly k if a pool was too small
    short = k - int(taken.sum())
    if short > 0:
        rest = np.where(~taken)[0]
        add = rest[np.argsort(-er[rest], kind="stable")[:short]]
        taken[add] = True
        src.update({i: "exploitation" for i in add})
    sel = np.where(taken)[0]
    return sel, er, src


def run(static: pd.DataFrame, cfg: dict, policy: str, r: float, eps: float, seed: int,
        keep_week: int | None = None, audit: bool = False, end_week: int | None = None,
        alerts: pd.DataFrame | None = None, keep_all: bool = False):
    sc, fc, mc = cfg["simulation"], cfg["features"], cfg["model"]
    opts = CYCLE.get(policy, {})
    rng = np.random.default_rng(seed)
    alpha = fc["alpha"]
    weeks = sorted(static.week.unique())
    end_week = end_week or sc["end_week"]
    feats = MODEL_FEATURES + (ENTITY_FEATURES if opts.get("entity") else [])
    revealed_parts: list[pd.DataFrame] = []
    rows, audits, keep, register, companies = [], [], {}, [], []
    model = None
    for w in weeks:
        if w > end_week:
            break
        b = static[static.week == w]
        revealed = pd.concat(revealed_parts) if revealed_parts else b.iloc[0:0].assign(rev_src="")
        b = b.join(risk_profiles(revealed, b, alpha))
        history = static[static.week < w] if (opts.get("entity") or keep_all) else None
        if opts.get("entity"):
            b = b.join(batch_features(revealed, history, b, w, cfg))
        if w < sc["start_week"]:  # warm start: random inspections only
            n_rev = int(round(sc["warm_reveal_share"] * len(b)))
            pos = rng.choice(len(b), size=n_rev, replace=False)
            revealed_parts.append(b.iloc[pos].assign(rev_src="warm"))
            if audit:
                audits.append({"week": w, "event": "reveal", "ids": set(b.id.iloc[pos])})
            continue
        if policy in NEEDS_MODEL or opts:
            if model is None or (w - sc["start_week"]) % sc.get("retrain_every", 1) == 0:
                model = RiskModel(n_estimators=mc["n_estimators"], learning_rate=mc["learning_rate"],
                                  num_leaves=mc["num_leaves"], seed=mc["seed"] + seed, features=list(feats))
                model.fit(revealed, calib_week=int(revealed.week.max()))
                if audit:
                    audits.append({"week": w, "event": "train", "ids": set(revealed.id),
                                   "train_max_week": int(revealed.week.max())})
            b = b.join(model.score(b))
        else:
            b = b.assign(p=np.nan, r_hat=np.nan, er=np.nan)
        k = int(round(r * len(b)))
        alert_rows = active_mask(b, alerts, w, cfg.get("trends", {}).get("persist_weeks", 2)) \
            if opts.get("trends") else np.zeros(len(b), bool)
        if opts.get("segments"):
            sel, score, src = _cycle_select(b, k, rng, cfg["cycle"], alert_rows, opts.get("trust_exploit", False))
        else:
            sel, score = select("mirsad" if opts else policy, b, k, eps, rng)
            src = {i: ("audit" if policy == "random" else "exploitation") for i in sel}
        lanes = assign_lanes(len(b), sel, score, k_orange=k)
        y, rev = b.label_fraud.values, b.label_revenue.values
        inj = (b.scheme.values == "injected")
        red, org, vert = lanes == LANE_ROUGE, lanes == LANE_ORANGE, lanes == LANE_VERT
        row = {
            "week": w, "N": len(b), "k": int(red.sum()),
            "fraud_total": int(y.sum()), "fraud_sel": int(y[red].sum()),
            "rev_total": float(rev.sum()), "rev_sel": float(rev[red].sum()),
            "rev_orange": float(rev[org].sum()), "rev_vert": float(rev[vert].sum()),
            "fraud_vert": int(y[vert].sum()), "n_vert": int(vert.sum()),
            "inj_total": int(inj.sum()), "inj_sel": int((inj & red).sum()),
            "rev_inj_total": float(rev[inj].sum()), "rev_inj_sel": float(rev[inj & red].sum()),
            "rev_hist_total": float(rev[~inj].sum()), "rev_hist_sel": float(rev[~inj & red].sum()),
            "n_new_imp_sel": int(b.is_new_importer.values[red].sum()),
            "brier": float(np.mean((b.p.values - y) ** 2)) if b.p.notna().all() else np.nan,
            "n_alert_rows": int(alert_rows.sum()),
        }
        if "segment" in b:  # ground-truth evaluation per tier (never used for decisions)
            for s_ in ["Confiance", "Standard", "Surveillé", "Critique"]:
                m = b.segment.values == s_
                row[f"n_{s_}"], row[f"fraud_{s_}"] = int(m.sum()), int(y[m].sum())
                row[f"rev_{s_}"] = float(rev[m].sum())
                row[f"fraud_vert_{s_}"] = int(y[m & vert].sum())
        srcs = np.array([src.get(i, "") for i in range(len(b))], dtype=object)
        for s_ in ["exploitation", "exploration", "audit"]:
            m = srcs == s_
            row[f"k_{s_}"], row[f"fraud_{s_}"], row[f"inj_{s_}"] = int(m.sum()), int(y[m].sum()), int((inj & m).sum())
        rows.append(row)
        if keep_week is not None and w == keep_week:
            keep = {"batch": b.assign(lane=lanes, selected_by=srcs, alert=alert_rows), "revealed": revealed,
                    "model": model}
        if keep_all:
            reg = b.assign(lane=lanes, selected_by=srcs, alert=alert_rows)
            if "segment" not in reg:
                reg = reg.join(batch_features(revealed, history, reg, w, cfg))
            register.append(reg[[c for c in REGISTER_COLS if c in reg.columns]])
            ct = company_table(revealed, history, w, cfg)
            companies.append(ct.reset_index(names="importer").assign(week=w)[
                ["week", "importer", "ent_mean", "ent_sd", "ent_neff", "ent_trend", "link_risk", "segment",
                 "ent_a", "ent_b"]])
        chosen = b.iloc[sel].assign(rev_src=[src.get(i, "exploitation") for i in sel])
        revealed_parts.append(chosen.drop(columns=["p", "r_hat", "er"]))
        if audit:
            audits.append({"week": w, "event": "reveal", "ids": set(b.id.iloc[sel])})
    out = pd.DataFrame(rows).assign(policy=policy, r=r, eps=eps, seed=seed)
    if keep_all:
        keep["register"] = pd.concat(register, ignore_index=True)
        keep["companies"] = pd.concat(companies, ignore_index=True)
    return out, keep, audits


def summarize(weekly: pd.DataFrame, w0: int) -> dict:
    s = weekly.sum(numeric_only=True)
    after = weekly[weekly.week >= w0].sort_values("week")
    a = after.sum(numeric_only=True)
    cum = after.inj_sel.cumsum().values
    first5 = after.week.values[np.argmax(cum >= 5)] if (cum >= 5).any() else np.nan
    wk_rate = (after.rev_inj_sel / after.rev_inj_total.replace(0, np.nan)).fillna(0).values
    half = after.week.values[np.argmax(wk_rate >= 0.5)] if (wk_rate >= 0.5).any() else np.nan
    out = {
        "precision_at_k": s.fraud_sel / max(s.k, 1),
        "recall": s.fraud_sel / max(s.fraud_total, 1),
        "revenue_at_k": s.rev_sel / max(s.rev_total, 1),
        "revenue_hist_at_k": s.rev_hist_sel / max(s.rev_hist_total, 1),
        "tnd_per_inspection": s.rev_sel / max(s.k, 1),
        "injected_recall_rev": a.rev_inj_sel / max(a.rev_inj_total, 1),
        "injected_recall_n": a.inj_sel / max(a.inj_total, 1),
        "false_green_fraud": s.fraud_vert / max(s.fraud_total, 1),
        "false_green_rev": s.rev_vert / max(s.rev_total, 1),
        "share_vert": s.n_vert / max(s.N, 1),
        "weeks_to_5_scheme_catches": (first5 - w0) if first5 == first5 else np.nan,
        "weeks_to_50pct_weekly_scheme_capture": (half - w0) if half == half else np.nan,
        "brier": float(weekly.brier.mean()) if "brier" in weekly and weekly.brier.notna().any() else np.nan,
    }
    if "n_Confiance" in weekly:
        for s_ in ["Confiance", "Standard", "Surveillé", "Critique"]:
            out[f"fraud_rate_{s_}"] = s[f"fraud_{s_}"] / max(s[f"n_{s_}"], 1)
            out[f"volume_share_{s_}"] = s[f"n_{s_}"] / max(s.N, 1)
        out["false_green_Confiance"] = s["fraud_vert_Confiance"] / max(s["n_Confiance"], 1)
    return out
