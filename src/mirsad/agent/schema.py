"""Dossier JSON schema (strict, OpenAI structured outputs compatible)."""

HYP_TYPES = ["sous-évaluation", "fausse espèce", "fausse origine", "réseau", "autre"]
CONF = ["faible", "moyen", "élevé"]
LANES = ["Rouge", "Orange", "Vert"]

_ids = {"type": "array", "items": {"type": "string"}}

DOSSIER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["case_id", "voie", "montant_en_jeu_TND", "probabilite_fraude", "resume", "faits",
                 "hypotheses", "base_legale", "controles_recommandes", "incertitudes", "niveau_confiance"],
    "properties": {
        "case_id": {"type": "string"},
        "voie": {"type": "string", "enum": LANES},
        "montant_en_jeu_TND": {"type": "number"},
        "probabilite_fraude": {"type": "number"},
        "resume": {"type": "string"},
        "faits": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["texte", "evidence_ids"],
            "properties": {"texte": {"type": "string"}, "evidence_ids": _ids}}},
        "hypotheses": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["type", "justification", "evidence_ids"],
            "properties": {"type": {"type": "string", "enum": HYP_TYPES},
                           "justification": {"type": "string"}, "evidence_ids": _ids}}},
        "base_legale": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["chunk_id", "source", "extrait"],
            "properties": {"chunk_id": {"type": "string"}, "source": {"type": "string"},
                           "extrait": {"type": "string"}}}},
        "controles_recommandes": {"type": "array", "items": {"type": "string"}},
        "incertitudes": {"type": "array", "items": {"type": "string"}},
        "niveau_confiance": {"type": "string", "enum": CONF},
    },
}

RESPONSE_FORMAT = {"type": "json_schema",
                   "json_schema": {"name": "dossier_mirsad", "strict": True, "schema": DOSSIER_SCHEMA}}
