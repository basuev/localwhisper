import numpy as np


def test_transcriber_empty_audio(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.transcribe(b"") == ""
    assert not t._model_loaded


def test_transcriber_unload(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    t._model_loaded = True
    t._mlx_whisper = "fake"
    t._unload()
    assert not t._model_loaded
    assert t._mlx_whisper is None


def test_hallucination_filtered():
    from localwhisper.transcriber import _is_hallucination

    hallucinations = [
        "Продолжение следует...",
        "Субтитры делал кто-то",
        "Подписывайтесь на канал!",
        "Спасибо за просмотр.",
        "amara.org",
    ]
    for text in hallucinations:
        assert _is_hallucination(text), f"should filter: {text!r}"


def test_normal_text_passes_filter():
    from localwhisper.transcriber import _is_hallucination

    normal = [
        "Привет, как дела?",
        "Напиши мне функцию для сортировки",
        "Сделай deploy на продакшен",
    ]
    for text in normal:
        assert not _is_hallucination(text), f"should pass: {text!r}"


def test_transcriber_language_mutable(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.language == "ru"
    t.language = "en"
    assert t.language == "en"


def test_transcriber_transcribe_array(default_config):
    from unittest.mock import Mock

    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    t._model_loaded = True
    t._mlx_whisper = Mock()
    t._mlx_whisper.transcribe.return_value = {"text": "hello world"}

    audio = np.random.randn(16000).astype(np.float32)
    result = t.transcribe_array(audio)

    assert result == "hello world"
    call_args = t._mlx_whisper.transcribe.call_args
    assert isinstance(call_args[0][0], np.ndarray)


def test_transcriber_transcribe_array_empty(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.transcribe_array(np.array([], dtype=np.float32)) == ""
    assert not t._model_loaded
