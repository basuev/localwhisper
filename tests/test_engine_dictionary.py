import yaml


def test_engine_applies_dictionary(tmp_path, default_config):
    from localwhisper.dictionary import UserDictionary
    from localwhisper.engine import LocalWhisperEngine
    from localwhisper.events import PostProcessingDone

    dict_path = tmp_path / "dictionary.yaml"
    dict_path.write_text(yaml.dump([{"from": "деплой", "to": "deploy"}]))

    engine = LocalWhisperEngine(default_config)
    engine._dictionary = UserDictionary(dict_path)

    results = []
    engine.on(PostProcessingDone, lambda e: results.append(e.processed_text))
    engine._config["postprocess"] = False
    engine._finish_with_text("деплой на сервер")

    assert results == ["deploy на сервер"]


def test_engine_feedback_adds_to_dictionary(tmp_path, default_config):
    from localwhisper.dictionary import UserDictionary
    from localwhisper.engine import LocalWhisperEngine

    dict_path = tmp_path / "dictionary.yaml"
    engine = LocalWhisperEngine(default_config)
    engine._dictionary = UserDictionary(dict_path)
    engine._last_inserted_text = "деплой на сервер"

    result = engine.feedback("deploy на сервер")

    assert result.added == [("деплой", "deploy")]
    assert result.conflicts == []
    assert engine._dictionary.entries == [("деплой", "deploy")]


def test_engine_feedback_ignores_unrelated_text(tmp_path, default_config):
    from localwhisper.dictionary import UserDictionary
    from localwhisper.engine import LocalWhisperEngine

    dict_path = tmp_path / "dictionary.yaml"
    engine = LocalWhisperEngine(default_config)
    engine._dictionary = UserDictionary(dict_path)
    engine._last_inserted_text = "деплой на сервер"

    result = engine.feedback("совсем другой текст который не имеет отношения к вставке")

    assert result is None


def test_engine_feedback_no_last_text(default_config):
    from localwhisper.engine import LocalWhisperEngine

    engine = LocalWhisperEngine(default_config)
    result = engine.feedback("anything")
    assert result is None
