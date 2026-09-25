"""Deterministic investigation + template dossier, built only from tool outputs.

Used when no LLM key is available, or when the LLM dossier fails validation twice.
"""
from __future__ import annotations

import time

from ..explain import fmt
from .tools import call_tool


def run_tools(case_id: str) -> list[dict]:
    """Fixed investigation plan; returns a trace in the same format as the LLM loop."""
    trace = []

    def step(name, **args):
        t = time.time()
        out = call_tool(name, args)
        trace.append({"step": len(trace) + 1, "tool": name, "args": args, "output": out,
                      "duree_ms": round(1000 * (time.time() - t))})
        return out

    risk = step("get_risk_assessment", case_id=case_id)
    decl = step("get_declaration", case_id=case_id)
    if "erreur" in decl or "erreur" in risk:
        return trace
    step("get_entity_history", kind="importateur", entity_id=decl["importateur"])
    step("find_links", importer_id=decl["importateur"], declarant_id=decl["declarant"])
    step("get_peer_prices", hs6=decl["sh6"], country=decl["pays_origine"])
    step("find_similar_cases", case_id=case_id, k=3)
    if "description_commerciale" in decl:
        step("check_tariff_classification", case_id=case_id)
    step("get_mirror_evidence", hs_code=decl["sh6"][:2])
    top = (risk.get("facteurs_shap") or [{}])[0].get("variable", "")
    q = ("valeur en douane sous-évaluation contrôle" if top.startswith(("z_uv", "l_uv", "l_cif"))
         else "contrôle douanier déclaration fraude")
    step("search_regulations", query=f"{q} {decl['sh6']}", k=4)
    return trace


def _out(trace, tool):
    for s in trace:
        if s["tool"] == tool:
            return s["output"]
    return {}


def scorer_view(trace) -> dict:
    r = _out(trace, "get_risk_assessment")
    return {"voie": r["voie"], "probabilite_fraude": r["probabilite_fraude"],
            "montant_en_jeu_TND": r["montant_en_jeu_TND"]}


def build(case_id: str, trace: list[dict]) -> dict:
    risk, decl = _out(trace, "get_risk_assessment"), _out(trace, "get_declaration")
    hist, lk = _out(trace, "get_entity_history"), _out(trace, "find_links")
    peer, sim = _out(trace, "get_peer_prices"), _out(trace, "find_similar_cases")
    tarif, regs = _out(trace, "check_tariff_classification"), _out(trace, "search_regulations")
    rid, did = risk["evidence_id"], decl["evidence_id"]

    faits = [{"texte": risk["texte"], "evidence_ids": [rid]}]
    for f in risk.get("facteurs_shap", []):
        if f["contribution_shap"] > 0:
            faits.append({"texte": f["texte"], "evidence_ids": [f["evidence_id"]]})
    if decl.get("alerte_injection"):
        a = decl["alerte_injection"]
        faits.append({"texte": a["texte"], "evidence_ids": [a["evidence_id"]]})
    pe = peer.get("meme_sh6_meme_pays") or {}
    if not pe.get("n"):
        pe = peer.get("meme_sh6_tous_pays") or {}
    if pe.get("n") and pe.get("prix_unitaire_median") and decl.get("prix_unitaire") is not None:
        faits.append({"texte": f"Prix unitaire déclaré {fmt(decl['prix_unitaire'], 2)} contre une médiane de "
                               f"{fmt(pe['prix_unitaire_median'], 2)} sur {pe['n']} déclarations passées comparables.",
                      "evidence_ids": [did, peer["evidence_id"]]})
    if hist.get("declarations_passees") is not None:
        faits.append({"texte": f"L'importateur {decl['importateur']} a {hist['declarations_passees']} déclarations "
                               f"passées ; {hist['controles_passes_reveles']} contrôles avec résultat connu, dont "
                               f"{hist['fraudes_confirmees']} fraudes confirmées.",
                      "evidence_ids": [hist["evidence_id"]]})
    if lk.get("declarant_risque_eleve"):
        d = lk["declarants"][0]
        faits.append({"texte": f"Le déclarant {d['declarant']} présente un taux de fraude lissé de "
                               f"{fmt(100 * d['taux_fraude_lisse'], 1)} % sur {d['controles_reveles']} contrôles révélés.",
                      "evidence_ids": [lk["evidence_id"]]})
    for s in sim.get("resultats_similaires", [])[:2]:
        faits.append({"texte": f"Fraude confirmée similaire : {s['case_id']} (semaine {s['semaine']}, SH {s['sh6']}), "
                               f"revenu redressé {fmt(s['revenu_redresse_TND'], 0)} TND simulés.",
                      "evidence_ids": [s["evidence_id"]]})

    hyps = []
    shap_vars = {f["variable"]: f for f in risk.get("facteurs_shap", []) if f["contribution_shap"] > 0}
    if (pe.get("prix_unitaire_median") and decl.get("prix_unitaire") is not None
            and decl["prix_unitaire"] < 0.7 * pe["prix_unitaire_median"]):
        hyps.append({"type": "sous-évaluation",
                     "justification": f"Prix unitaire déclaré {fmt(decl['prix_unitaire'], 2)}, inférieur à la médiane "
                                      f"{fmt(pe['prix_unitaire_median'], 2)} des déclarations comparables.",
                     "evidence_ids": [did, peer["evidence_id"]]})
    elif shap_vars.keys() & {"z_uv", "z_uv_kg", "l_uv", "l_uv_kg"}:
        v = next(shap_vars[k] for k in ["z_uv", "z_uv_kg", "l_uv", "l_uv_kg"] if k in shap_vars)
        hyps.append({"type": "sous-évaluation", "justification": v["texte"], "evidence_ids": [v["evidence_id"]]})
    if tarif.get("alerte_espece"):
        hyps.append({"type": "fausse espèce", "justification": tarif.get("texte", "Espèce déclarée hors du top 3."),
                     "evidence_ids": [tarif["evidence_id"]]})
    if lk.get("declarant_risque_eleve") or "risk_importer" in shap_vars or "risk_imp_hs4" in shap_vars:
        ev = [lk["evidence_id"]] + [shap_vars[k]["evidence_id"] for k in ["risk_importer", "risk_imp_hs4"]
                                    if k in shap_vars]
        hyps.append({"type": "réseau",
                     "justification": "Historique de fraudes révélées sur l'importateur et/ou ses déclarants liés "
                                      "(voir taux de fraude lissés).", "evidence_ids": ev})
    if decl.get("alerte_injection"):
        hyps.append({"type": "autre", "justification": "Tentative de manipulation de l'outil via la description "
                                                       "commerciale : à signaler.",
                     "evidence_ids": [decl["alerte_injection"]["evidence_id"]]})
    if not hyps:
        hyps.append({"type": "autre", "justification": "Profil de risque élevé selon le modèle (voir facteurs SHAP).",
                     "evidence_ids": [rid]})

    base = []
    for c in regs.get("resultats", []):
        if c["chunk_id"].startswith("LEG-"):
            base.append({"chunk_id": c["chunk_id"], "source": c["source"],
                         "extrait": " ".join(c["text"].split()[:30])})
            break
    incert = ["Données synthétiques (BACUDA) et montants simulés : aucune conclusion sur des cas réels.",
              "Les fraudes connues ne proviennent que des déclarations inspectées par le passé (étiquettes sélectives)."]
    if not base:
        incert.insert(0, "Base légale : à confirmer par l'agent (aucun texte juridique chargé dans le corpus).")
    if decl.get("alerte_injection"):
        incert.append("La description commerciale contient des instructions : elle a été ignorée (donnée non fiable).")
    p = risk["probabilite_fraude"]
    conf = "élevé" if p >= 0.8 and len(faits) >= 4 else "moyen" if p >= 0.5 else "faible"
    top_fact = next((f["texte"] for f in risk.get("facteurs_shap", []) if f["contribution_shap"] > 0), "")
    resume = (f"Déclaration {case_id} ({decl['importateur']}, SH {decl['sh6']}) orientée en voie {risk['voie']} "
              f"par le scoreur. Principal facteur : {top_fact}")
    resume = " ".join(resume.split()[:78])
    return {
        "case_id": case_id, "voie": risk["voie"],
        "montant_en_jeu_TND": risk["montant_en_jeu_TND"], "probabilite_fraude": p,
        "resume": resume, "faits": faits, "hypotheses": hyps, "base_legale": base,
        "controles_recommandes": risk.get("controles_recommandes_regles", []),
        "incertitudes": incert, "niveau_confiance": conf,
    }
