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
    from localwhisper.postprocessor import PostProcessor

    default_config["translate_to"] = "English"
    pp = PostProcessor(default_config)
    assert pp.translate_to == "English"
    prompt = pp._build_prompt()
    assert "English" in prompt
    assert "Russian" not in prompt
    assert default_config["postprocess_prompt"] not in prompt


def test_postprocessor_no_translate_prompt(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.translate_to is None
    prompt = pp._build_prompt()
    assert prompt == default_config["postprocess_prompt"]


def test_postprocessor_set_translate_to(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    pp.set_translate_to("Japanese")
    assert pp.translate_to == "Japanese"
    assert "Japanese" in pp._build_prompt()

    pp.set_translate_to(None)
    assert pp.translate_to is None
    prompt = pp._build_prompt()
    assert prompt == default_config["postprocess_prompt"]


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

    assert captured["timeout"] == 30
