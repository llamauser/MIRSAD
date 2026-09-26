"""LLM providers, tried in the order set by config `llm.order` (demo: OpenAI API first, local Ollama as fallback;
production: local only, on-premises).

- Local: OpenAI-compatible endpoint of Ollama (default http://localhost:11434/v1), model from config.
- API: keys from the environment / .env (OPENAI_API_KEYS comma-separated and/or OPENAI_API_KEY), never
  logged; on authentication, permission or rate-limit errors the next key is tried.
Callers always keep a deterministic fallback when no provider is available or validation fails.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache

from .config import ROOT, load_config


def _load_dotenv():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def keys() -> list[str]:
    _load_dotenv()
    ks = [k.strip() for k in os.environ.get("OPENAI_API_KEYS", "").split(",") if k.strip()]
    single = os.environ.get("OPENAI_API_KEY", "").strip()
    if single and single not in ks:
        ks.insert(0, single)
    return ks


def mask(k: str) -> str:
    return f"{k[:7]}…{k[-4:]}" if len(k) > 12 else "***"


@dataclass
class Provider:
    name: str            # "local" | "api"
    model: str
    model_small: str
    base_url: str | None = None
    extra_body: dict = field(default_factory=dict)
    time_budget_s: float | None = None
    json_mode: str = "json_schema"  # "json_schema" (strict) or "json_object" (lighter, validated afterwards)
    context_tokens: int | None = None  # local context window (None = large API context)
    key_idx: int = 0

    @property
    def label(self) -> str:
        return f"{'LLM local' if self.name == 'local' else 'API OpenAI'} ({self.model})"

    def _client(self, i: int = 0):
        from openai import OpenAI
        if self.name == "local":
            return OpenAI(base_url=self.base_url, api_key="ollama", timeout=600, max_retries=0)
        return OpenAI(api_key=keys()[i], timeout=120, max_retries=2)

    def chat(self, small: bool = False, **kwargs):
        """chat.completions.create with this provider's model and options (key rotation for the API)."""
        kwargs.setdefault("model", self.model_small if small else self.model)
        if self.extra_body:
            kwargs["extra_body"] = {**self.extra_body, **kwargs.get("extra_body", {})}
        if self.name == "local":
            return self._client().chat.completions.create(**kwargs)
        import openai
        ks, last = keys(), None
        for attempt in range(len(ks)):
            i = (self.key_idx + attempt) % len(ks)
            try:
                out = self._client(i).chat.completions.create(**kwargs)
                self.key_idx = i
                return out
            except (openai.AuthenticationError, openai.PermissionDeniedError, openai.RateLimitError) as e:
                last = e
                print(f"[llm] API key {i + 1}/{len(ks)} ({mask(ks[i])}) failed: {type(e).__name__}; trying next")
        raise last or RuntimeError("aucune clé OpenAI")


def _ollama_has(base_url: str, model: str) -> tuple[bool, str]:
    root = base_url.rsplit("/v1", 1)[0]
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=3) as r:
            names = {m["name"] for m in json.load(r).get("models", [])}
    except Exception:
        return False, "serveur Ollama injoignable"
    if model in names or f"{model}:latest" in names:
        return True, "ok"
    return False, f"modèle {model} absent d'Ollama (voir ollama/Modelfile)"


@lru_cache(maxsize=1)
def providers() -> tuple[Provider, ...]:
    """Available providers in priority order (checked once per process)."""
    cfg = load_config()["llm"]
    out = []
    loc = cfg.get("local", {})
    order = cfg.get("order", ["local", "api"])
    if loc.get("enabled", False):
        ok, why = _ollama_has(loc["base_url"], loc["model"])
        print(f"[llm] local {loc['model']}: {why}")
        if ok:
            out.append(Provider("local", loc["model"], loc.get("model_small", loc["model"]), loc["base_url"],
                                dict(loc.get("extra_body") or {}), loc.get("time_budget_s"),
                                loc.get("json_mode", "json_schema"), loc.get("context_tokens")))
    api = cfg.get("api", {})
    if api.get("enabled", False) and keys():
        p = Provider("api", api["model"], api.get("model_small", api["model"]))
        try:
            import openai
            for i in range(len(keys())):
                try:
                    p._client(i).models.retrieve(api["model"])
                    p.key_idx = i
                    break
                except (openai.AuthenticationError, openai.PermissionDeniedError, openai.RateLimitError):
                    continue
            else:
                raise RuntimeError("aucune clé valide")
            out.append(p)
            print(f"[llm] api {api['model']}: ok ({len(keys())} clé(s))")
        except Exception as e:
            print(f"[llm] api {api['model']}: indisponible ({type(e).__name__})")
    return tuple(sorted(out, key=lambda pr: order.index(pr.name) if pr.name in order else len(order)))


def available() -> bool:
    return bool(providers())
