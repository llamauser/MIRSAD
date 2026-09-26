"""Entity links (networkx): importer-declarant and importer-HS4 edges from past declarations.
Fraud rates on neighbours use revealed (inspected) labels only."""
from __future__ import annotations

import networkx as nx
import pandas as pd


def build_graph(history: pd.DataFrame) -> nx.Graph:
    g = nx.Graph()
    e = history.groupby(["importer", "declarant"]).size().reset_index(name="n")
    g.add_weighted_edges_from((("I:" + a, "D:" + b, n) for a, b, n in e.itertuples(index=False)))
    e = history.groupby(["importer", "hs4"]).size().reset_index(name="n")
    g.add_weighted_edges_from((("I:" + a, "H:" + b, n) for a, b, n in e.itertuples(index=False)))
    return g


def smoothed_rate(revealed: pd.DataFrame, col: str, alpha: float = 10):
    p0 = revealed.label_fraud.mean() if len(revealed) else 0.05
    g = revealed.groupby(col).label_fraud.agg(["sum", "count"])
    return ((g["sum"] + alpha * p0) / (g["count"] + alpha)).rename("risk"), g["count"], p0


def links(g: nx.Graph, revealed: pd.DataFrame, importer: str, declarant: str | None = None,
          risky_threshold: float = 0.25) -> dict:
    dec_rate, dec_n, p0 = smoothed_rate(revealed, "declarant")
    imp_rate, imp_n, _ = smoothed_rate(revealed, "importer")
    node = "I:" + importer
    decls = [n[2:] for n in g.neighbors(node) if n.startswith("D:")] if node in g else []
    if declarant and declarant not in decls:
        decls.append(declarant)
    dec_info = []
    for d in decls:
        dec_info.append({"declarant": d, "taux_fraude_lisse": round(float(dec_rate.get(d, p0)), 4),
                         "controles_reveles": int(dec_n.get(d, 0)),
                         "degre_importateurs": g.degree("D:" + d) if ("D:" + d) in g else 0})
    co_imps = set()
    for d in decls:
        if ("D:" + d) in g:
            co_imps |= {n[2:] for n in g.neighbors("D:" + d) if n.startswith("I:")}
    co_imps.discard(importer)
    co = [{"importer": i, "taux_fraude_lisse": round(float(imp_rate.get(i, p0)), 4),
           "controles_reveles": int(imp_n.get(i, 0))} for i in co_imps]
    co = sorted(co, key=lambda x: -x["taux_fraude_lisse"])[:5]
    risky = [d for d in dec_info if d["taux_fraude_lisse"] >= risky_threshold and d["controles_reveles"] >= 5]
    return {
        "importateur": importer,
        "degre": g.degree(node) if node in g else 0,
        "nouvel_importateur": node not in g,
        "declarants": sorted(dec_info, key=lambda x: -x["taux_fraude_lisse"])[:5],
        "importateurs_les_plus_risques_partageant_un_declarant": co,
        "n_importateurs_partageant_un_declarant": len(co_imps),
        "taux_fraude_moyen_des_5_plus_risques": round(float(pd.Series([c["taux_fraude_lisse"] for c in co]).mean()), 4) if co else None,
        "note": "Un importateur partageant un déclarant n'est pas en soi « à risque » : voir son taux de fraude lissé.",
        "declarant_risque_eleve": bool(risky),
        "nouvel_importateur_lie_a_declarant_risque": bool(node not in g and risky),
        "seuil_risque_declarant": risky_threshold,
    }
