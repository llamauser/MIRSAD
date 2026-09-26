"""Risk model: calibrated P(fraud) and expected revenue R_hat -> ER = p * R_hat."""
from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from .features import MODEL_FEATURES


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


@dataclass
class RiskModel:
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 31
    seed: int = 42
    features: list = field(default_factory=lambda: list(MODEL_FEATURES))
    clf: object = None
    iso: object = None
    reg: object = None
    r_fallback: float = 0.0
    p_fallback: float = 0.05

    def _X(self, df):
        return df[self.features].astype(float).values

    def fit(self, train: pd.DataFrame, calib_week: int | None = None) -> "RiskModel":
        """train: revealed rows with features + labels. The most recent revealed week is
        held out for isotonic calibration when it is large enough; otherwise raw scores."""
        y = train.label_fraud.values.astype(int)
        self.p_fallback = float(y.mean()) if len(y) else 0.05
        use_cal = False
        if calib_week is not None:
            cal = train.week == calib_week
            yc = y[cal.values]
            use_cal = cal.sum() >= 30 and 0 < yc.sum() < len(yc) and (~cal).sum() >= 100
        fit_mask = (train.week != calib_week).values if use_cal else np.ones(len(train), bool)
        yf = y[fit_mask]
        self.clf = None
        if len(yf) >= 30 and 0 < yf.sum() < len(yf):
            spw = (len(yf) - yf.sum()) / max(yf.sum(), 1)
            self.clf = lgb.LGBMClassifier(
                n_estimators=self.n_estimators, learning_rate=self.learning_rate,
                num_leaves=self.num_leaves, scale_pos_weight=spw, random_state=self.seed,
                subsample=0.8, subsample_freq=1, colsample_bytree=0.8, min_child_samples=10,
                n_jobs=1, verbose=-1)
            self.clf.fit(self._X(train[fit_mask]), yf)
        self.iso = None
        if use_cal and self.clf is not None:
            # Platt scaling on the held-out most recent week (smooth, monotone, never a 0.9999 plateau like the
            # isotonic step function). Still fitted on inspected rows only: probabilities remain selection-biased.
            raw = self.clf.predict_proba(self._X(train[~fit_mask]))[:, 1]
            self.iso = LogisticRegression(C=1.0).fit(_logit(raw).reshape(-1, 1), y[~fit_mask])
        # revenue regressor on revealed frauds only
        frauds = train[train.label_fraud == 1]
        self.r_fallback = float(frauds.label_revenue.median()) if len(frauds) else 0.0
        self.reg = None
        if len(frauds) >= 30:
            self.reg = lgb.LGBMRegressor(
                n_estimators=self.n_estimators // 2, learning_rate=self.learning_rate,
                num_leaves=15, random_state=self.seed, min_child_samples=5, n_jobs=1, verbose=-1)
            self.reg.fit(self._X(frauds), np.log1p(frauds.label_revenue.clip(lower=0).values))
        return self

    def predict_raw(self, df):
        if self.clf is None:
            return np.full(len(df), self.p_fallback)
        return self.clf.predict_proba(self._X(df))[:, 1]

    def predict_p(self, df):
        raw = self.predict_raw(df)
        if self.iso is not None:
            raw = self.iso.predict_proba(_logit(raw).reshape(-1, 1))[:, 1]
        return np.clip(raw, 0.001, 0.98)

    def predict_r(self, df):
        if self.reg is None:
            return np.full(len(df), self.r_fallback)
        return np.expm1(self.reg.predict(self._X(df))).clip(min=0)

    def score(self, df) -> pd.DataFrame:
        p = self.predict_p(df)
        r = self.predict_r(df)
        return pd.DataFrame({"p": p, "r_hat": r, "er": p * r}, index=df.index)


def revenue_at(scores: np.ndarray, revenue: np.ndarray, share: float) -> float:
    """Share of total revenue captured when inspecting the top `share` by score."""
    k = max(1, int(round(share * len(scores))))
    idx = np.argsort(-scores)[:k]
    tot = revenue.sum()
    return float(revenue[idx].sum() / tot) if tot > 0 else 0.0


def eval_scores(y, rev, p, er) -> dict:
    return {
        "auc_roc": float(roc_auc_score(y, p)),
        "auc_pr": float(average_precision_score(y, p)),
        "base_rate": float(np.mean(y)),
        "revenue_at_10pct_by_p": revenue_at(p, rev, 0.10),
        "revenue_at_10pct_by_er": revenue_at(er, rev, 0.10),
    }
