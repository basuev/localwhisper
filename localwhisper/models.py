import json
import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CODEX_MODELS_CACHE = Path.home() / ".codex" / "models_cache.json"


def fetch_ollama_models(ollama_url: str) -> list[str]:
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        log.debug("Failed to fetch Ollama models", exc_info=True)
        return []


def load_codex_models(cache_path: Path = CODEX_MODELS_CACHE) -> list[str]:
    try:
        data = json.loads(cache_path.read_text())
        return [
            m["slug"]
            for m in data.get("models", [])
            if m.get("visibility") == "list"
        ]
    except Exception:
        log.debug("Failed to load Codex models cache", exc_info=True)
        return []
