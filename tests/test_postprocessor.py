def test_postprocessor_empty_text(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.process("") == ""


def test_postprocessor_empty_text_openai(default_config):
    from localwhisper.postprocessor import PostProcessor

    default_config["postprocessor"] = "openai"
    pp = PostProcessor(default_config)
    assert pp.process("") == ""


def test_postprocessor_backend_selection(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp_ollama = PostProcessor(default_config)
    assert pp_ollama.backend == "ollama"

    default_config["postprocessor"] = "openai"
    pp_openai = PostProcessor(default_config)
    assert pp_openai.backend == "openai"


def test_postprocessor_switch(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.backend == "ollama"
    assert pp.ollama_model == default_config["ollama_model"]

    pp.switch("openai", "gpt-4o")
    assert pp.backend == "openai"
    assert pp.openai_model == "gpt-4o"

    pp.switch("ollama", "llama3:8b")
    assert pp.backend == "ollama"
    assert pp.ollama_model == "llama3:8b"


def test_postprocessor_builds_translate_prompt(default_config):
    from localwhisper.postprocessor import POSTPROCESS_PROMPT, PostProcessor

    default_config["translate_to"] = "English"
    pp = PostProcessor(default_config)
    prompt = pp._build_prompt()
    assert POSTPROCESS_PROMPT in prompt
    assert "English" in prompt


def test_postprocessor_no_translate_prompt(default_config):
    from localwhisper.postprocessor import POSTPROCESS_PROMPT, PostProcessor

    pp = PostProcessor(default_config)
    prompt = pp._build_prompt()
    assert prompt == POSTPROCESS_PROMPT


def test_postprocessor_set_translate_to(default_config):
    from localwhisper.postprocessor import POSTPROCESS_PROMPT, PostProcessor

    pp = PostProcessor(default_config)
    pp.set_translate_to("Japanese")
    assert pp.translate_to == "Japanese"
    prompt = pp._build_prompt()
    assert POSTPROCESS_PROMPT in prompt
    assert "Japanese" in prompt

    pp.set_translate_to(None)
    assert pp.translate_to is None
    assert pp._build_prompt() == POSTPROCESS_PROMPT


def test_ollama_request_has_no_thinking_params(default_config, monkeypatch):
    from unittest.mock import Mock

    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)

    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["json"] = json
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"message": {"content": "test"}}
        return resp

    monkeypatch.setattr("localwhisper.postprocessor.requests.post", mock_post)
    pp.process("hello")

    assert "think" not in captured["json"]
    system_msg = captured["json"]["messages"][0]["content"]
    assert "/no_think" not in system_msg


def test_build_prompt_with_corrections(default_config, tmp_path):
    from localwhisper.corrections import CorrectionsStore
    from localwhisper.postprocessor import POSTPROCESS_PROMPT, PostProcessor

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("деплой на сервер", "deploy на сервер")
    store.add("запушить в мастер", "push to master")

    pp = PostProcessor(default_config)
    pp.set_corrections_store(store)
    prompt = pp._build_prompt("деплой на стейджинг")

    assert POSTPROCESS_PROMPT in prompt
    assert "деплой на сервер" in prompt
    assert "deploy на сервер" in prompt


def test_build_prompt_no_corrections_unchanged(default_config):
    from localwhisper.postprocessor import POSTPROCESS_PROMPT, PostProcessor

    pp = PostProcessor(default_config)
    assert pp._build_prompt() == POSTPROCESS_PROMPT


def test_build_prompt_respects_char_budget(default_config, tmp_path):
    from localwhisper.corrections import CorrectionsStore
    from localwhisper.postprocessor import PostProcessor

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    for i in range(20):
        store.add(f"original text number {i}", f"corrected text number {i}")

    default_config["max_fewshot_chars"] = 300
    pp = PostProcessor(default_config)
    pp.set_corrections_store(store)
    prompt = pp._build_prompt("original text")

    fewshot_start = prompt.find("Learn from these patterns:")
    assert fewshot_start != -1
    fewshot_section = prompt[fewshot_start:]
    assert len(fewshot_section) <= 400
    assert prompt.count("Example") < 20


def test_build_prompt_with_translation_and_corrections(default_config, tmp_path):
    from localwhisper.corrections import CorrectionsStore
    from localwhisper.postprocessor import PostProcessor

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("тест", "test")

    default_config["translate_to"] = "English"
    pp = PostProcessor(default_config)
    pp.set_corrections_store(store)
    prompt = pp._build_prompt("тест")

    assert "English" in prompt
    assert "тест" in prompt
    assert "test" in prompt


def test_process_passes_text_to_build_prompt(default_config, tmp_path, monkeypatch):
    from unittest.mock import Mock

    from localwhisper.corrections import CorrectionsStore
    from localwhisper.postprocessor import PostProcessor

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("деплой на сервер", "deploy на сервер")

    pp = PostProcessor(default_config)
    pp.set_corrections_store(store)

    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["system_content"] = json["messages"][0]["content"]
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"message": {"content": "result"}}
        return resp

    monkeypatch.setattr("localwhisper.postprocessor.requests.post", mock_post)
    pp.process("деплой на стейджинг")

    assert "деплой на сервер" in captured["system_content"]


def test_ollama_timeout_is_30s(default_config, monkeypatch):
    from unittest.mock import Mock

    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)

    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"message": {"content": "test"}}
        return resp

    monkeypatch.setattr("localwhisper.postprocessor.requests.post", mock_post)
    pp.process("hello")

    assert captured["timeout"] == 120
