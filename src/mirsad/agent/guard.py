"""Prompt-injection pre-filter for untrusted text (declaration descriptions, tenders)."""
import re

PATTERNS = [
    r"\bignore\b", r"\binstructions?\b", r"\bclassify\s+as\b", r"\bsystem\s*:", r"\bassistant\s*:",
    r"\btu\s+dois\b", r"\bignore[rz]?\s+les\b", r"\boublie[rz]?\b", r"\bclasse[rz]?\s+(en|comme)\b",
    r"\bvoie\s+verte\b", r"\bgreen\s+lane\b", r"\bdisregard\b", r"\bprompt\b",
    r"تجاهل", r"صنّف", r"صنف", r"تعليمات",
]
_RX = [re.compile(p, re.IGNORECASE) for p in PATTERNS]
OPEN, CLOSE = "<<<DONNEES_NON_FIABLES>>>", "<<<FIN>>>"


def scan(text: str) -> dict:
    hits = [p.pattern for p in _RX if p.search(text or "")]
    return {"injection_flag": int(bool(hits)), "motifs_detectes": hits}


def wrap(text: str) -> str:
    """Wrap untrusted text; strip any delimiter look-alikes inside it."""
    t = (text or "").replace(OPEN, "").replace(CLOSE, "")
    return f"{OPEN} {t} {CLOSE}"
