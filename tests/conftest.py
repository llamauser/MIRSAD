import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")


@pytest.fixture(scope="session")
def cfg():
    from mirsad.config import load_config
    return load_config()


@pytest.fixture(scope="session")
def static():
    import pandas as pd
    f = ROOT / "data/processed/static_drift.parquet"
    if not f.exists():
        pytest.skip("run scripts/01_build_features.py first")
    return pd.read_parquet(f)
