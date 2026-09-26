"""Agent tools: pure Python functions returning JSON with evidence ids, plus OpenAI schemas.

All tools only see the past of the demo week (declared data of past weeks, labels of
past *inspected* rows). Free text from declarations is untrusted and wrapped.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from ..config import p
from ..context import get_context
from ..explain import Explainer, fmt, recommended_checks
from ..features import MODEL_FEATURES
from ..graph import build_graph, links
from ..rag import get_corpus, sentences
from . import guard

DESC_PATH = "data/espece/demo_case_descriptions.json"


@lru_cache(maxsize=1)
def _explainer():
    return Explainer(get_context().model)


@lru_cache(maxsize=1)
def _graph():
    return build_graph(get_context().history)


@lru_cache(maxsize=1)
def _descriptions() -> dict:
    f = p(DESC_PATH)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _num(x, d=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def _case(case_id: str) -> pd.Series:
    ctx = get_context()
    if case_id not in ctx.batch.index:
        raise KeyError(f"déclaration inconnue : {case_id}")
    return ctx.batch.loc[case_id]


def get_declaration(case_id: str) -> dict:
    r = _case(case_id)
    out = {
        "evidence_id": f"DECL-{case_id}",
        "case_id": case_id, "date": str(r.date.date()), "semaine": int(r.week),
        "importateur": r.importer, "declarant": r.declarant, "pays_origine": r.country,
        "bureau": r.office, "code_sh10": r.hs10, "sh6": r.hs6, "sh4": r.hs4,
        "quantite": _num(r.quantity, 0), "poids_brut_kg": _num(r.weight, 0),
        "valeur_fob": _num(r.fob, 0), "valeur_cif": _num(r.cif, 0), "taxes": _num(r.taxes, 0),
        "prix_unitaire": _num(r.cif / r.quantity if r.quantity else None, 2),
        "unite_monetaire": "TND simulés (données synthétiques)",
    }
    d = _descriptions().get(case_id)
    if d:
        g = guard.scan(d["description"])
        out["description_commerciale"] = guard.wrap(d["description"])
        out["description_origine"] = d.get("origine", "construite par l'équipe")
        out["injection_flag"] = g["injection_flag"]
        if g["injection_flag"]:
            out["alerte_injection"] = {
                "evidence_id": f"GUARD-{case_id}",
                "texte": "Tentative d'injection d'instructions détectée dans la description "
                         "(texte traité comme donnée non fiable ; priorité relevée).",
                "motifs": g["motifs_detectes"]}
    return out


def get_risk_assessment(case_id: str) -> dict:
    r = _case(case_id)
    facts = _explainer().facts(r, case_id)
    L = links(_graph(), get_context().revealed, r.importer, r.declarant)
    return {
        "evidence_id": f"RISK-{case_id}",
        "case_id": case_id,
        "voie": r.lane,
        "probabilite_fraude": _num(r.p, 4),
        "revenu_attendu_si_fraude_TND": _num(r.r_hat, 0),
        "montant_en_jeu_TND": _num(r.er, 0),
        "segment": r.get("segment"),
        "motif_selection": WHY.get(r.get("selected_by", ""), "non sélectionnée"),
        "alerte_tendance_active": bool(r.get("alert", False)),
        "texte": (f"Voie {r.lane} décidée par le scoreur déterministe : P(fraude) = "
                  f"{fmt(100 * r.p, 2 if r.p > 0.99 else 1)} %, montant en jeu (P × revenu attendu) = {fmt(r.er, 0)} TND simulés."),
        "facteurs_shap": facts,
        "controles_recommandes_regles": recommended_checks(r, facts, L),
        "note": "Scores issus du modèle LightGBM calibré ; l'agent ne peut pas modifier la voie.",
    }


WHY = {"exploitation": "montant en jeu parmi les plus élevés de la semaine (exploitation)",
       "exploration": "entreprise peu connue : contrôle d'exploration (échantillonnage de Thompson)",
       "audit": "audit aléatoire d'une entreprise « Confiance » (mesure du faux-vert)"}


def get_company_profile(importer_id: str) -> dict:
    """② score dynamique de conformité + ③ segment, lus dans le registre de risque (semaine de la démo)."""
    from .. import register
    ctx = get_context()
    h = register.company_history(importer_id)
    h = h[h.week <= ctx.week]
    if not len(h):
        return {"evidence_id": f"COMP-{importer_id}", "erreur": "entreprise absente du registre"}
    cur = h.iloc[-1]
    past = register.outcomes(importer_id, ctx.week)
    lo = max(0.0, cur.ent_mean - 1.645 * cur.ent_sd)
    hi = min(1.0, cur.ent_mean + 1.645 * cur.ent_sd)
    return {
        "evidence_id": f"COMP-{importer_id}",
        "entreprise": importer_id, "semaine": int(cur.week),
        "score_risque_0_100": _num(100 * cur.ent_mean, 1),
        "intervalle_90_pct": [_num(100 * lo, 1), _num(100 * hi, 1)],
        "controles_effectifs": _num(cur.ent_neff, 1),
        "tendance_4_semaines_points": _num(100 * cur.ent_trend, 1),
        "risque_reseau_declarants_pct": _num(100 * cur.link_risk, 1),
        "segment": cur.segment,
        "controles_passes": [{"evidence_id": f"CTRL-{r.id}", "semaine": int(r.week), "sh6": r.hs6,
                              "motif": r.selected_by, "resultat": "fraude" if r.label_fraud else "conforme",
                              "redressement_TND": _num(r.label_revenue, 0)} for r in past.tail(5).itertuples()],
        "note": ("Score = loi bêta a posteriori (a priori : taux de fraude des contrôles aléatoires), mise à jour par "
                 "chaque contrôle, avec une demi-vie de 12 semaines. Segment : Surveillé = peu connue, Critique = "
                 "connue et risquée, Confiance = connue et conforme."),
    }


def get_trend_alerts(hs_code: str) -> dict:
    """⑦ alertes de tendance (signaux faibles) sur le chapitre / la position SH, jusqu'à la semaine de la démo."""
    from .. import register
    ctx = get_context()
    al = register.alerts()
    hs = str(hs_code)
    if len(al):
        al = al[(al.week <= ctx.week) & (((al.cle_type == "hs2") & (al.cle == hs[:2])) |
                                         ((al.cle_type == "hs4") & (al.cle == hs[:4])))]
    return {"evidence_id": f"TREND-{hs[:4]}",
            "alertes": [{"evidence_id": r.alert_id, "signal": r.signal, "cle": r.cle, "semaine": int(r.week),
                         "valeur": _num(r.valeur, 2), "reference": _num(r.reference, 2), "z": _num(r.z, 1)}
                        for r in al.tail(5).itertuples()] if len(al) else [],
            "note": "Signaux calculés sur les seules données déclarées (sans étiquette) ; indicateur, pas une preuve."}


def get_entity_history(kind: str, entity_id: str) -> dict:
    ctx = get_context()
    col = {"importateur": "importer", "importer": "importer", "declarant": "declarant",
           "déclarant": "declarant", "bureau": "office", "office": "office",
           "pays": "country", "country": "country"}.get(kind, kind)
    if col not in ("importer", "declarant", "office", "country"):
        return {"evidence_id": f"HIST-{kind}-{entity_id}", "erreur": f"type d'entité inconnu : {kind}"}
    h = ctx.history[ctx.history[col] == entity_id]
    rv = ctx.revealed[ctx.revealed[col] == entity_id]
    p0 = ctx.revealed.label_fraud.mean()
    n_i, n_f = len(rv), int(rv.label_fraud.sum())
    return {
        "evidence_id": f"HIST-{col}-{entity_id}",
        "type": col, "id": entity_id,
        "declarations_passees": int(len(h)),
        "premiere_declaration": str(h.date.min().date()) if len(h) else None,
        "valeur_cif_totale": _num(h.cif.sum(), 0),
        "principales_positions_sh4": h.hs4.value_counts().head(5).to_dict(),
        "controles_passes_reveles": n_i,
        "fraudes_confirmees": n_f,
        "taux_fraude_lisse": _num((n_f + 10 * p0) / (n_i + 10), 4),
        "revenu_redresse_passe_TND": _num(rv.label_revenue.sum(), 0),
        "note": "Historique limité aux semaines passées ; fraudes connues uniquement pour les déclarations inspectées.",
    }


def get_peer_prices(hs6: str, country: str | None = None) -> dict:
    h = get_context().history
    out = {"evidence_id": f"PEER-{hs6}-{country or 'ALL'}", "sh6": hs6, "pays": country}
    for name, sub in [("meme_sh6_meme_pays", h[(h.hs6 == hs6) & (h.country == country)] if country else None),
                      ("meme_sh6_tous_pays", h[h.hs6 == hs6])]:
        if sub is None:
            continue
        uv = (sub.cif / sub.quantity).replace([np.inf, -np.inf], np.nan).dropna()
        out[name] = {"n": int(len(sub)),
                     "prix_unitaire_median": _num(uv.median(), 2) if len(uv) else None,
                     "prix_unitaire_p10": _num(uv.quantile(0.1), 2) if len(uv) else None,
                     "prix_unitaire_p90": _num(uv.quantile(0.9), 2) if len(uv) else None,
                     "taux_taxation_median_pct": _num(100 * (sub.taxes / sub.cif).median(), 1) if len(sub) else None}
    return out


def find_similar_cases(case_id: str, k: int = 3) -> dict:
    ctx = get_context()
    r = _case(case_id)
    frauds = ctx.revealed[ctx.revealed.label_fraud == 1]
    feats = [f for f in MODEL_FEATURES if not f.startswith("risk_")]
    X = frauds[feats].astype(float).fillna(0).values
    mu, sd = X.mean(0), X.std(0) + 1e-9
    x = (r[feats].astype(float).fillna(0).values - mu) / sd
    d = np.sqrt((((X - mu) / sd - x) ** 2).sum(1))
    order = np.argsort(d)[:k]
    res = []
    for i in order:
        f = frauds.iloc[i]
        res.append({"evidence_id": f"SIM-{f.id}", "case_id": f.id, "semaine": int(f.week),
                    "importateur": f.importer, "sh6": f.hs6, "pays": f.country,
                    "revenu_redresse_TND": _num(f.label_revenue, 0), "distance": _num(d[i], 2)})
    return {"evidence_id": f"SIMSET-{case_id}", "base": "fraudes confirmées lors de contrôles passés",
            "n_base": int(len(frauds)), "resultats_similaires": res}


def find_links(importer_id: str, declarant_id: str | None = None) -> dict:
    out = links(_graph(), get_context().revealed, importer_id, declarant_id)
    out["evidence_id"] = f"LINK-{importer_id}"
    return out


def check_tariff_classification(case_id: str) -> dict:
    d = _descriptions().get(case_id)
    if not d:
        return {"evidence_id": f"TARIF-{case_id}", "disponible": False,
                "raison": "aucune description commerciale dans ce jeu de données"}
    try:
        from ..espece import classify
        res = classify(d["description"], declared_hs6=_case(case_id).hs6, cif=float(_case(case_id).cif))
    except Exception as e:  # never crash the dossier
        return {"evidence_id": f"TARIF-{case_id}", "disponible": False, "raison": f"module espèce indisponible ({e})"}
    res["evidence_id"] = f"TARIF-{case_id}"
    return res


def get_mirror_evidence(hs_code: str) -> dict:
    f = p("data/processed/mirror.parquet")
    hs2 = str(hs_code)[:2]
    if not f.exists():
        return {"evidence_id": f"MIRROR-{hs2}", "disponible": False, "raison": "données miroir indisponibles"}
    m = pd.read_parquet(f)
    m = m[m.hs2 == hs2]
    return {"evidence_id": f"MIRROR-{hs2}", "disponible": bool(len(m)),
            "nature": "indicateur macro de priorisation (Tunisie réelle, UN Comtrade), pas une preuve pour cette déclaration",
            "flux": m.sort_values("leak_usd", ascending=False).head(5)[
                ["partner", "year", "M_cif_usd", "X_fob_usd", "gap_log", "leak_usd"]].round(3).to_dict("records")}


def search_regulations(query: str, k: int = 4) -> dict:
    """Legal chunks first (data/legal), then HS descriptions. Texts are verbatim corpus chunks."""
    k = max(1, min(int(k), 8))
    corpus = get_corpus()
    legal = corpus.search(query, k=min(k, 4), kind="legal")
    res = legal if legal else corpus.search(query, k=2, kind="hs")  # HS labels only when no legal text matches
    return {"evidence_id": "REG-" + hashlib.md5(query.encode("utf-8")).hexdigest()[:8],
            "requete": query,
            "corpus_juridique_disponible": any(c["kind"] == "legal" for c in corpus.chunks),
            # legal chunks: only their quotable verbatim sentences (compact for small local models);
            # the validator checks quotes against the full chunk text in the corpus
            "resultats": [({"chunk_id": r["chunk_id"], "source": r["source"],
                            "phrases_citables": sentences(r["text"])[:4]} if r["chunk_id"].startswith("LEG-")
                           else {"chunk_id": r["chunk_id"], "source": r["source"], "text": r["text"]})
                          for r in res],
            "note": ("Aucun texte juridique n'a été chargé : base légale à confirmer par l'agent."
                     if not legal else "Extraits verbatim du corpus chargé (chunk_id LEG-…) ; les HS-… sont des "
                                       "libellés du Système harmonisé, pas des textes juridiques.")}


TOOLS = {
    "get_company_profile": get_company_profile,
    "get_trend_alerts": get_trend_alerts,
    "get_declaration": get_declaration,
    "get_risk_assessment": get_risk_assessment,
    "get_entity_history": get_entity_history,
    "get_peer_prices": get_peer_prices,
    "find_similar_cases": find_similar_cases,
    "find_links": find_links,
    "check_tariff_classification": check_tariff_classification,
    "get_mirror_evidence": get_mirror_evidence,
    "search_regulations": search_regulations,
}


def _fn(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required,
                       "additionalProperties": False}}}


_S = {"type": "string"}
TOOL_SCHEMAS = [
    _fn("get_risk_assessment", "Score déterministe (P fraude, montant en jeu, voie) et facteurs SHAP. À appeler en premier.",
        {"case_id": _S}, ["case_id"]),
    _fn("get_company_profile", "Score dynamique de conformité de l'entreprise (0-100, incertitude, tendance, "
        "segment) et ses contrôles passés, depuis le registre de risque.", {"importer_id": _S}, ["importer_id"]),
    _fn("get_trend_alerts", "Alertes de tendance (signaux faibles) sur le chapitre ou la position SH.",
        {"hs_code": _S}, ["hs_code"]),
    _fn("get_declaration", "Champs de la déclaration (et description commerciale non fiable si disponible).",
        {"case_id": _S}, ["case_id"]),
    _fn("get_entity_history", "Historique passé d'une entité : importateur, declarant, bureau ou pays.",
        {"kind": {"type": "string", "enum": ["importateur", "declarant", "bureau", "pays"]}, "entity_id": _S},
        ["kind", "entity_id"]),
    _fn("get_peer_prices", "Prix unitaires des déclarations comparables passées (même SH6, même pays).",
        {"hs6": _S, "country": _S}, ["hs6", "country"]),
    _fn("find_similar_cases", "Fraudes confirmées passées les plus proches (kNN).",
        {"case_id": _S, "k": {"type": "integer"}}, ["case_id", "k"]),
    _fn("find_links", "Liens importateur-déclarant et importateurs liés, avec taux de fraude révélés.",
        {"importer_id": _S, "declarant_id": _S}, ["importer_id", "declarant_id"]),
    _fn("check_tariff_classification", "Vérification de l'espèce tarifaire (SH) si une description existe.",
        {"case_id": _S}, ["case_id"]),
    _fn("get_mirror_evidence", "Indicateur macro miroir UN Comtrade pour le chapitre SH (priorisation, pas preuve).",
        {"hs_code": _S}, ["hs_code"]),
    _fn("search_regulations", "Recherche dans le corpus réglementaire chargé (extraits verbatim).",
        {"query": _S, "k": {"type": "integer"}}, ["query", "k"]),
]


def call_tool(name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"erreur": f"outil inconnu : {name}"}
    try:
        return TOOLS[name](**args)
    except Exception as e:
        return {"erreur": f"{type(e).__name__}: {e}"}
