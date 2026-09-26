"""Shared UI helpers: paths, banner, style, cached loaders (precomputed files only)."""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

NAVY, TEAL, INK2 = "#0b1f3a", "#0f766e", "#52514e"
LANE_COLORS = {"Rouge": "#c0392b", "Orange": "#d9822b", "Vert": "#1e8449"}
LANE_BG = {"Rouge": "#fbe9e7", "Orange": "#fdf1e3", "Vert": "#e8f5ec"}

CSS = f"""
<style>
.block-container {{padding-top: 1.2rem; max-width: 1300px;}}
.mirsad-banner {{background:{NAVY}; color:#fff; padding:.45rem .9rem; border-radius:6px; font-size:.85rem;
  margin-bottom:.8rem; border-left:5px solid {TEAL};}}
.kpi {{background:#fff; border:1px solid #e3e7ec; border-radius:8px; padding:.8rem 1rem; height:100%;}}
.kpi .v {{font-size:1.9rem; font-weight:700; color:{NAVY}; line-height:1.1;}}
.kpi .l {{font-size:.82rem; color:{INK2};}}
.kpi .s {{font-size:.75rem; color:#7a7a75; margin-top:.2rem;}}
.chip {{display:inline-block; background:#e6f2f1; color:{TEAL}; border-radius:10px; padding:0 .45rem;
  font-size:.72rem; margin:0 .15rem; font-family:monospace;}}
.lane {{display:inline-block; border-radius:4px; padding:.1rem .6rem; font-weight:600; color:#fff;}}
.badge {{display:inline-block; border-radius:4px; padding:.1rem .55rem; font-size:.8rem; font-weight:600;
  border:1px solid; margin-right:.3rem;}}
.caveat {{background:#fff8e6; border-left:4px solid #d9a400; padding:.6rem .9rem; border-radius:4px;
  font-size:.88rem;}}
</style>
"""


def page(title: str, icon: str = "🛰️"):
    st.set_page_config(page_title=f"MIRSAD — {title}", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="mirsad-banner"><b>MIRSAD مرصاد</b> · Prototype : données synthétiques et scénario '
                'de fraude simulé. Aucun résultat ne porte sur des déclarations réelles.</div>',
                unsafe_allow_html=True)


def kpi(col, value: str, label: str, sub: str = ""):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div>'
                 f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)


def lane_html(lane: str) -> str:
    return f'<span class="lane" style="background:{LANE_COLORS.get(lane, "#777")}">{lane}</span>'


def fr(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x: float, d: int = 1) -> str:
    return fr(100 * x, d) + " %"


@st.cache_data
def load_json(rel: str):
    f = ROOT / rel
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


@st.cache_data
def load_parquet(rel: str):
    f = ROOT / rel
    return pd.read_parquet(f) if f.exists() else None


@st.cache_data
def load_csv(rel: str, **kw):
    f = ROOT / rel
    return pd.read_csv(f, **kw) if f.exists() else None


def metric(metrics: dict, policy: str, r: float, eps: float, name: str):
    for m in metrics["runs"]:
        if m["policy"] == policy and abs(m["r"] - r) < 1e-9 and abs(m["eps"] - eps) < 1e-9:
            return m[name]
    return None
