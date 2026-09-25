"""Demo context: the scored demo week, what was known before it, and the model.

Everything an agent tool may see is restricted to the past of the demo week
(declared data of past weeks, labels of past *inspected* rows only).
"""
from __future__ import annotations

import pickle
from functools import lru_cache

import pandas as pd

from .config import load_config, p


class Context:
    def __init__(self):
        self.cfg = load_config()
        self.batch = pd.read_parquet(p("results/demo_week.parquet"))
        self.revealed = pd.read_parquet(p("results/demo_revealed.parquet"))
        self.model = pickle.load(open(p("results/demo_model.pkl"), "rb"))
        self.week = int(self.batch.week.iloc[0])
        static = pd.read_parquet(p("data/processed/static_drift.parquet"))
        self.history = static[static.week < self.week]  # declared data only, no labels used
        self.batch = self.batch.set_index("id", drop=False)
        self.extra_cases: dict[str, dict] = {}  # e.g. the injection demo case

    def case(self, case_id: str) -> pd.Series:
        return self.batch.loc[case_id]


@lru_cache(maxsize=1)
def get_context() -> Context:
    return Context()
