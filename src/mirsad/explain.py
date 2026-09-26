"""SHAP -> French fact sentences with exact values, plus rule-based recommended checks."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

# shap optionally imports OpenCV for image maskers; a local OpenCV built for NumPy 1.x crashes noisily on import.
# We never use image explainers, so make that optional import fail cleanly instead.
sys.modules.setdefault("cv2", None)
import shap  # noqa: E402

from .features import MODEL_FEATURES


def fmt(x: float, d: int = 1) -> str:
    """French number format: space thousands separator, comma decimals."""
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def _level(lv: str) -> str:
    return {"hs6/country": "même SH6 et même pays", "hs6": "même SH6", "hs4": "même SH4",
            "hs2": "même chapitre", "global": "ensemble des déclarations"}.get(lv, lv)


def fact_text(f: str, row: pd.Series) -> str:
    """French sentence for one feature of one declaration, using exact values."""
    hs6 = row.get("hs6", "")
    if f in ("z_uv", "z_uv_kg", "z_kg_unit", "z_tax_rt"):
        z = float(row[f])
        side = "sous" if z < 0 else "au-dessus de"
        what = {"z_uv": "Prix unitaire déclaré", "z_uv_kg": "Valeur déclarée par kg",
                "z_kg_unit": "Poids par unité", "z_tax_rt": "Taux de taxation déclaré"}[f]
        lvl = _level(str(row.get(f + "_level", "")))
        med = row.get(f + "_med")
        if f == "z_uv":
            val = f"{fmt(row.cif / row.quantity, 2)} par unité contre une médiane de {fmt(np.expm1(med), 2)}"
        elif f == "z_uv_kg":
            val = f"{fmt(row.cif / row.weight, 2)} par kg contre une médiane de {fmt(np.expm1(med), 2)}"
        elif f == "z_kg_unit":
            val = f"{fmt(row.weight / row.quantity, 1)} kg par unité contre une médiane de {fmt(np.expm1(med), 1)}"
        else:
            val = f"{fmt(100 * row.tax_rt, 1)} % contre une médiane de {fmt(100 * med, 1)} %"
        return (f"{what} {fmt(abs(z), 1)} écarts robustes {side} la médiane des déclarations "
                f"comparables ({lvl}, SH {hs6}) : {val}.")
    risk_names = {"risk_importer": ("de l'importateur", "importer"),
                  "risk_declarant": ("du déclarant", "declarant"),
                  "risk_office": ("du bureau", "office"), "risk_country": ("du pays d'origine", "country"),
                  "risk_hs6": ("de la sous-position SH", "hs6"),
                  "risk_imp_hs4": ("du couple importateur × SH4", "hs4")}
    if f in risk_names:
        lab, col = risk_names[f]
        return (f"Taux de fraude lissé {lab} {row.get(col, '')} : {fmt(100 * row[f], 1)} % "
                f"(sur les contrôles passés révélés).")
    if f == "is_new_importer":
        return ("Importateur jamais vu avant cette semaine." if row[f] else
                "Importateur déjà connu.")
    if f == "is_new_combo":
        return (f"Première déclaration de cet importateur dans la position SH4 {row.hs4}." if row[f]
                else f"L'importateur a déjà déclaré en SH4 {row.hs4}.")
    if f == "hist_count_importer":
        return f"{int(row[f])} déclarations passées de cet importateur."
    if f == "hist_count_declarant":
        return f"{int(row[f])} déclarations passées de ce déclarant."
    if f == "n_inspected_importer":
        return f"{int(row[f])} contrôles passés de cet importateur avec résultat connu."
    if f == "days_since_first":
        return f"Importateur connu depuis {int(row[f])} jours."
    if f == "iso_score":
        return f"Score d'anomalie multivariée (Isolation Forest) : {fmt(row[f], 2)}."
    if f == "l_cif":
        return f"Valeur CIF déclarée : {fmt(row.cif, 0)} TND simulés."
    if f == "l_qty":
        return f"Quantité déclarée : {fmt(row.quantity, 0)}."
    if f == "tax_rt":
        return f"Taux de taxation déclaré (taxes/CIF) : {fmt(100 * row[f], 1)} %."
    if f == "fob_cif":
        return f"Rapport FOB/CIF : {fmt(row[f], 2)}."
    if f == "l_uv":
        return f"Prix unitaire déclaré : {fmt(row.cif / row.quantity, 2)} par unité."
    if f == "l_uv_kg":
        return f"Valeur déclarée par kg : {fmt(row.cif / row.weight, 2)}."
    if f == "l_kg_unit":
        return f"Poids par unité : {fmt(row.weight / row.quantity, 1)} kg."
    return f"{f} = {row[f]}"


class Explainer:
    def __init__(self, model):
        self.model = model
        self.ex = shap.TreeExplainer(model.clf) if model.clf is not None else None

    def facts(self, row: pd.Series, case_id: str, top: int = 5) -> list[dict]:
        if self.ex is None:
            return []
        x = row[MODEL_FEATURES].astype(float).values.reshape(1, -1)
        sv = self.ex.shap_values(x)
        sv = sv[1] if isinstance(sv, list) else sv
        sv = np.asarray(sv).reshape(-1)
        order = np.argsort(-np.abs(sv))[:top]
        out = []
        for i in order:
            f = MODEL_FEATURES[i]
            out.append({
                "evidence_id": f"SHAP-{case_id}-{f}",
                "variable": f,
                "valeur": round(float(row[f]), 4),
                "contribution_shap": round(float(sv[i]), 4),
                "sens": "augmente le risque" if sv[i] > 0 else "diminue le risque",
                "texte": fact_text(f, row),
            })
        return out


def recommended_checks(row: pd.Series, facts: list[dict], links: dict | None = None) -> list[str]:
    """Rule-based recommended controls (not LLM-generated)."""
    checks = []
    pos = {f["variable"] for f in facts if f["contribution_shap"] > 0}
    if (row.get("z_uv", 0) < -1.5 or row.get("z_uv_kg", 0) < -1.5 or
            pos & {"z_uv", "z_uv_kg", "l_uv", "l_uv_kg", "l_cif"}):
        checks += ["Demander le contrat de vente et la facture commerciale",
                   "Exiger la preuve de paiement (virement bancaire)",
                   "Comparer le prix avec les déclarations comparables (même SH6, même origine)"]
    if pos & {"risk_hs6", "z_tax_rt", "tax_rt"} or abs(row.get("z_tax_rt", 0)) > 2:
        checks += ["Examen physique de la marchandise / prélèvement d'échantillon (vérification de l'espèce)"]
    if row.get("z_uv", 0) > 2:
        checks += ["Vérifier la quantité et l'espèce déclarées (valeur unitaire anormalement élevée)"]
    if abs(row.get("z_kg_unit", 0)) > 2 or pos & {"z_kg_unit", "l_kg_unit"}:
        checks += ["Pesage de la marchandise"]
    if row.get("is_new_importer", 0) and links and links.get("declarant_risque_eleve"):
        checks += ["Vérification de l'identité de l'importateur et du registre du commerce"]
    elif row.get("is_new_importer", 0) or row.get("is_new_combo", 0):
        checks += ["Vérification de l'identité et de l'activité déclarée de l'importateur"]
    if not checks:
        checks = ["Contrôle documentaire standard"]
    return list(dict.fromkeys(checks))
