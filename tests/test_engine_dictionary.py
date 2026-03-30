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
    from localwhisper.corrections import CorrectionsStore
    from localwhisper.dictionary import UserDictionary
    from localwhisper.engine import LocalWhisperEngine

    dict_path = tmp_path / "dictionary.yaml"
    corr_path = tmp_path / "corrections.yaml"
    engine = LocalWhisperEngine(default_config)
    engine._dictionary = UserDictionary(dict_path)
    engine._corrections = CorrectionsStore(corr_path)

    result = engine.feedback("деплой на сервер", "deploy на сервер")

    assert result.added == [("деплой", "deploy")]
    assert result.conflicts == []
    assert engine._dictionary.entries == [("деплой", "deploy")]


def test_engine_feedback_no_change_returns_none(default_config):
    from localwhisper.engine import LocalWhisperEngine

    engine = LocalWhisperEngine(default_config)
    result = engine.feedback("same text", "same text")
    assert result is None


def test_engine_feedback_saves_correction(tmp_path, default_config):
    from localwhisper.corrections import CorrectionsStore
    from localwhisper.dictionary import UserDictionary
    from localwhisper.engine import LocalWhisperEngine

    dict_path = tmp_path / "dictionary.yaml"
    corr_path = tmp_path / "corrections.yaml"
    engine = LocalWhisperEngine(default_config)
    engine._dictionary = UserDictionary(dict_path)
    engine._corrections = CorrectionsStore(corr_path)

    result = engine.feedback("деплой на сервер", "deploy на сервер")

    assert result.correction_saved is True

    store = CorrectionsStore(corr_path)
    assert len(store.entries) == 1
    assert store.entries[0].original == "деплой на сервер"
    assert store.entries[0].corrected == "deploy на сервер"


def test_engine_corrections_store_connected_to_postprocessor(tmp_path, default_config):
    from localwhisper.engine import LocalWhisperEngine

    engine = LocalWhisperEngine(default_config)
    assert engine._postprocessor._corrections_store is engine._corrections
