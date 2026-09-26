"""Dossier validator: every claim must be traceable to the tool trace.

Rejects when:
- an evidence_id is not present in any tool output of the trace;
- a number in resume / faits.texte / hypotheses.justification is not found in any
  tool output (tolerance: thousands spaces, decimal comma, rounding, % <-> fraction);
- a base_legale chunk_id was not retrieved, or its extrait is not verbatim in the chunk
  (or is longer than 40 words);
- voie / probabilite_fraude / montant_en_jeu_TND differ from the deterministic scorer.
"""
from __future__ import annotations

import json
import re

from .schema import DOSSIER_SCHEMA

NUM_RX = re.compile(r"(?<![A-Za-z0-9_\-])\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?(?![A-Za-z0-9])"
                    r"|(?<![A-Za-z0-9_\-])\d+(?:[.,]\d+)?(?![A-Za-z0-9])")
TRIVIAL = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0}
# semantic guard: each hypothesis type must cite at least one evidence of a compatible kind
_VALUE_FEATS = ("z_uv", "z_uv_kg", "l_uv", "l_uv_kg", "l_cif", "tax_rt", "z_tax_rt", "fob_cif", "iso_score")
_RISK_FEATS = ("risk_importer", "risk_declarant", "risk_imp_hs4", "n_inspected_importer", "hist_count_importer",
               "is_new_importer", "is_new_combo")


def _compatible(hyp: str, eid: str, prefixes: tuple) -> bool:
    if not eid.startswith(prefixes):
        return False
    if eid.startswith("SHAP-"):
        feat = eid.split("-", 2)[-1]
        return feat in (_VALUE_FEATS if hyp == "sous-évaluation" else _RISK_FEATS if hyp == "réseau" else ())
    return True

HYP_EVIDENCE = {
    "sous-évaluation": ("DECL-", "PEER-", "SIM-", "SHAP-"),
    "fausse espèce": ("TARIF-",),
    "fausse origine": ("DECL-", "MIRROR-", "PEER-"),
    "réseau": ("LINK-", "HIST-", "SIM-", "SHAP-"),
}


def parse_num(s: str) -> tuple[float, int]:
    s = re.sub(r"[   ]", "", s).replace(",", ".")
    dec = len(s.split(".")[1]) if "." in s else 0
    return float(s), dec


def numbers_in_text(text: str) -> list[tuple[str, float, int]]:
    return [(m.group(0), *parse_num(m.group(0))) for m in NUM_RX.finditer(text or "")]


def _walk(obj, out: list):
    if isinstance(obj, dict):
        for v in obj.values():
            _walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        out.extend(v for _, v, _ in numbers_in_text(obj))


def evidence_ids_in(obj, out: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("evidence_id", "chunk_id") and isinstance(v, str):
                out.add(v)
            evidence_ids_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            evidence_ids_in(v, out)


class TraceIndex:
    def __init__(self, trace: list[dict]):
        self.outputs = [step["output"] for step in trace if "output" in step]
        self.ids: set[str] = set()
        evidence_ids_in(self.outputs, self.ids)
        nums: list[float] = []
        _walk(self.outputs, nums)
        self.keys: set[tuple[int, float]] = set()
        for v in nums:
            for c in (v, v * 100, v / 1000, v / 1e6):
                for d in range(0, 4):
                    self.keys.add((d, round(c, d)))
        # retrieved chunks: full text from the output if present, else from the corpus (outputs may only carry
        # the quotable sentences); a chunk counts only if it was actually returned by a tool in this trace
        self.chunks: dict[str, dict] = {}
        for o in self.outputs:
            for item in (o.get("resultats", []) if isinstance(o, dict) else []):
                if isinstance(item, dict) and "chunk_id" in item:
                    text = item.get("text")
                    if text is None:
                        from ..rag import get_corpus
                        text = get_corpus().by_id.get(item["chunk_id"], {}).get("text", "")
                    self.chunks[item["chunk_id"]] = {**item, "text": text}

    def has_number(self, v: float, dec: int) -> bool:
        if v in TRIVIAL:
            return True
        return (min(dec, 3), round(v, min(dec, 3))) in self.keys


def _schema_errors(d: dict) -> list[str]:
    errs = []
    for k in DOSSIER_SCHEMA["required"]:
        if k not in d:
            errs.append(f"champ manquant : {k}")
    return errs


def validate(dossier: dict, trace: list[dict], scorer: dict) -> list[str]:
    """Return a list of errors (empty = valid). scorer = {voie, probabilite_fraude, montant_en_jeu_TND}."""
    errs = _schema_errors(dossier)
    if errs:
        return errs
    idx = TraceIndex(trace)
    if dossier["voie"] != scorer["voie"]:
        errs.append(f"voie modifiée : {dossier['voie']} ≠ {scorer['voie']} (le scoreur décide)")
    if abs(float(dossier["probabilite_fraude"]) - float(scorer["probabilite_fraude"])) > 1e-3:
        errs.append("probabilite_fraude différente de celle du scoreur")
    if abs(float(dossier["montant_en_jeu_TND"]) - float(scorer["montant_en_jeu_TND"])) > 1.0:
        errs.append("montant_en_jeu_TND différent de celui du scoreur")
    items = [("resume", dossier["resume"], [])]
    items += [("faits", f["texte"], f["evidence_ids"]) for f in dossier["faits"]]
    items += [("hypotheses", h["justification"], h["evidence_ids"]) for h in dossier["hypotheses"]]
    for field, text, ids in items:
        for e in ids:
            if e not in idx.ids:
                errs.append(f"{field}: evidence_id inconnu '{e}'")
        for raw, v, dec in numbers_in_text(text):
            if not idx.has_number(v, dec):
                errs.append(f"{field}: nombre '{raw}' introuvable dans les sorties d'outils")
    for h in dossier["hypotheses"]:
        ok_prefix = HYP_EVIDENCE.get(h["type"])
        if ok_prefix and not any(_compatible(h["type"], e, ok_prefix) for e in h["evidence_ids"]):
            errs.append(f"hypotheses: « {h['type']} » sans preuve compatible (attendu : {', '.join(ok_prefix)})")
    for f in dossier["faits"]:
        if not f["evidence_ids"]:
            errs.append(f"faits: fait sans evidence_id « {f['texte'][:50]} »")
    for b in dossier["base_legale"]:
        c = idx.chunks.get(b["chunk_id"])
        if c is None:
            errs.append(f"base_legale: chunk_id non récupéré '{b['chunk_id']}'")
            continue
        norm = lambda s: " ".join(s.split())  # noqa: E731
        if norm(b["extrait"]) not in norm(c["text"]):
            errs.append(f"base_legale: extrait non verbatim pour '{b['chunk_id']}'")
        if len(b["extrait"].split()) > 40:
            errs.append(f"base_legale: extrait > 40 mots pour '{b['chunk_id']}'")
    if len(dossier["resume"].split()) > 80:
        errs.append("resume > 80 mots")
    return errs


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, default=str)
