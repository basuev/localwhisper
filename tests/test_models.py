def test_fetch_ollama_models_success(monkeypatch):
    from unittest.mock import Mock

    from localwhisper.models import fetch_ollama_models

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "models": [{"name": "gemma3:4b"}, {"name": "llama3:8b"}]
    }

    import localwhisper.models as models_mod

    monkeypatch.setattr(models_mod.requests, "get", lambda *a, **kw: mock_resp)

    result = fetch_ollama_models("http://localhost:11434")
    assert result == ["gemma3:4b", "llama3:8b"]


def test_fetch_ollama_models_failure(monkeypatch):
    import localwhisper.models as models_mod
    from localwhisper.models import fetch_ollama_models

    monkeypatch.setattr(
        models_mod.requests,
        "get",
        lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("no ollama")),
    )

    assert fetch_ollama_models("http://localhost:11434") == []


def test_load_codex_models_success(tmp_path):
    import json

    from localwhisper.models import load_codex_models

    cache = tmp_path / "models_cache.json"
    cache.write_text(
        json.dumps(
            {
                "models": [
                    {"slug": "gpt-5.4", "visibility": "list"},
                    {"slug": "gpt-5.3-codex", "visibility": "list"},
                    {"slug": "gpt-5.1", "visibility": "hide"},
                ]
            }
        )
    )

    result = load_codex_models(cache_path=cache)
    assert result == ["gpt-5.4", "gpt-5.3-codex"]


def test_load_codex_models_missing_file(tmp_path):
    from localwhisper.models import load_codex_models

    result = load_codex_models(cache_path=tmp_path / "nonexistent.json")
    assert result == []


def test_recommended_ollama_models_survive_refresh():
    from localwhisper.constants import OLLAMA_MODELS
    from localwhisper.settings.tabs.models import merge_ollama_models

    recommended_ids = [model_id for model_id, _ in OLLAMA_MODELS]
    fetched = ["llama3:8b", "mistral:7b"]

    merged = merge_ollama_models(fetched)
    for rid in recommended_ids:
        assert rid in merged, f"{rid} must be in merged list"
    for f in fetched:
        assert f in merged
