"""Retrieval over the regulation corpus (data/legal/*.txt|md) and HS descriptions (BM25).

Legal files must start with a `SOURCE: <url or title>` line. We never generate
legal text: if data/legal/ is empty, only HS descriptions are searchable.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from rank_bm25 import BM25Okapi

from .config import p
from .textnorm import tokens

CHUNK, OVERLAP = 800, 150


def chunk_text(text: str, size: int = CHUNK, overlap: int = OVERLAP) -> list[str]:
    text = " ".join(text.split())
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        if i + size >= len(text):
            break
        i += size - overlap
    return out


def load_legal(folder: Path | None = None) -> list[dict]:
    folder = folder or p("data/legal")
    chunks = []
    for f in sorted(list(folder.glob("*.txt")) + list(folder.glob("*.md"))):
        lines = f.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].upper().startswith("SOURCE:"):
            print(f"[rag] skipped {f.name}: first line must be 'SOURCE: ...'")
            continue
        source = lines[0].split(":", 1)[1].strip()
        for i, c in enumerate(chunk_text("\n".join(lines[1:]))):
            cid = f"LEG-{f.stem[:20]}-{i:03d}"
            chunks.append({"chunk_id": cid, "source": source, "text": c, "kind": "legal"})
    return chunks


def load_hs(path: Path | None = None) -> list[dict]:
    path = path or p("data/hs/harmonized-system.csv")
    if not path.exists():
        return []
    hs = pd.read_csv(path, dtype=str)
    return [{"chunk_id": f"HS-{r.hscode}", "source": "Système harmonisé 2022 (datasets/harmonized-system, ODC-PDDL)",
             "text": f"{r.hscode} {r.description}", "kind": "hs"} for r in hs.itertuples()]


class Corpus:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.by_id = {c["chunk_id"]: c for c in chunks}
        self.bm25 = BM25Okapi([tokens(c["text"]) or ["_"] for c in chunks]) if chunks else None

    def search(self, query: str, k: int = 4, kind: str | None = None) -> list[dict]:
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(tokens(query))
        order = scores.argsort()[::-1]
        out = []
        for i in order:
            c = self.chunks[i]
            if kind and c["kind"] != kind:
                continue
            if scores[i] <= 0:
                break
            out.append({"chunk_id": c["chunk_id"], "source": c["source"], "text": c["text"],
                        "score": round(float(scores[i]), 3)})
            if len(out) >= k:
                break
        return out


def sentences(chunk_text: str, max_words: int = 40) -> list[str]:
    """Quotable sentences of a chunk: verbatim substrings (whitespace-normalised), each <= max_words words."""
    text = " ".join(chunk_text.split())
    out = []
    for s in re.split(r"(?<=[.;:])\s+", text):
        w = s.split()
        if w and w[0] == "Norme":  # WCO numbering residue ("6.4. Norme La douane ...")
            w = w[1:]
        if len(w) >= 6:
            out.append(" ".join(w[:max_words]))
    return out


def _sent_score(q: set, s: str) -> tuple:
    return (len(q & set(tokens(s))), -abs(len(s.split()) - 30))


def best_extract(chunk_text: str, query: str, max_words: int = 40) -> str:
    """Most query-relevant quotable sentence of a chunk."""
    q = set(tokens(query))
    sents = sentences(chunk_text, max_words)
    if not sents:
        return " ".join(chunk_text.split()[:max_words])
    return max(sents, key=lambda s: _sent_score(q, s))


def best_quote(results: list[dict], query: str) -> tuple[dict, str] | None:
    """Best (chunk, verbatim sentence) across several retrieved legal chunks."""
    q = set(tokens(query))
    cands = [(c, s) for c in results if c["chunk_id"].startswith("LEG-")
             for s in (c.get("phrases_citables") or sentences(c.get("text", "")))]
    return max(cands, key=lambda cs: _sent_score(q, cs[1])) if cands else None


@lru_cache(maxsize=1)
def get_corpus() -> Corpus:
    return Corpus(load_legal() + load_hs())


def legal_available() -> bool:
    return any(c["kind"] == "legal" for c in get_corpus().chunks)


def corpus_fingerprint() -> str:
    return hashlib.md5("".join(c["chunk_id"] for c in get_corpus().chunks).encode()).hexdigest()[:8]
