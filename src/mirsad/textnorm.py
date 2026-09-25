"""French/English-aware text normalisation for BM25."""
import re
import unicodedata

STOP = set("""le la les un une des du de d l et ou en au aux a pour par sur dans avec sans ce cette ces
son sa ses leur leurs qui que quoi dont est sont etre the of and or for to in on with without other
than not its their by as an at from be is are""".split())


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", norm(text))
    out = []
    for t in toks:
        if t in STOP or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("s"):  # light plural stemming (fr/en)
            t = t[:-1]
        out.append(t)
    return out
