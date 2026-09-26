"""Check the local LLM setup (Ollama) and create the `mirsad-qwen3:8b` variant from ollama/Modelfile.

Does not download anything by itself: if the base model is missing it prints the `ollama pull` command.
Run the Ollama server with OLLAMA_FLASH_ATTENTION=1 and OLLAMA_KV_CACHE_TYPE=q8_0 on 8 GB GPUs.
"""
import json
import shutil
import subprocess
import sys
import urllib.request

import _bootstrap  # noqa: F401

from mirsad.config import ROOT, load_config

cfg = load_config()["llm"]["local"]
root = cfg["base_url"].rsplit("/v1", 1)[0]
exe = shutil.which("ollama") or str(ROOT.home() / "AppData/Local/Programs/Ollama/ollama.exe")
try:
    with urllib.request.urlopen(f"{root}/api/tags", timeout=5) as r:
        names = {m["name"] for m in json.load(r)["models"]}
except Exception as e:
    sys.exit(f"Ollama server not reachable at {root} ({e}). Start it: `ollama serve`.")
print("installed:", sorted(names))
if "qwen3:8b" not in names:
    sys.exit("Base model missing. Run: ollama pull qwen3:8b   (~5 GB download)")
if cfg["model"] not in names:
    subprocess.run([exe, "create", cfg["model"], "-f", str(ROOT / "ollama" / "Modelfile")], check=True)
    print("created", cfg["model"])
else:
    print(cfg["model"], "already present")
