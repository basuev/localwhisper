def test_general_tab_language_mappings():
    from localwhisper.constants import SPEECH_LANGUAGES
    from localwhisper.settings.tabs.general import (
        _code_to_name,
        _name_to_code,
    )

    for code, name in SPEECH_LANGUAGES:
        assert _code_to_name[code] == name
        assert _name_to_code[name] == code

    assert _code_to_name["ru"] == "Russian"
    assert _name_to_code["English"] == "en"


def test_general_tab_hotkey_mappings():
    from localwhisper.settings.tabs.general import (
        HOTKEY_CHOICES,
        _hotkey_code_to_name,
        _hotkey_name_to_code,
    )

    for name, code in HOTKEY_CHOICES:
        assert _hotkey_name_to_code[name] == code
        assert _hotkey_code_to_name[code] == name

    assert _hotkey_name_to_code["Right Option"] == 61
    assert _hotkey_name_to_code["Fn"] == 63
    assert _hotkey_code_to_name[54] == "Right Command"


def test_models_tab_whisper_mappings():
    from localwhisper.constants import WHISPER_MODELS
    from localwhisper.settings.tabs.models import (
        WHISPER_DISPLAY_TO_ID,
        WHISPER_ID_TO_DISPLAY,
    )

    for model_id, display in WHISPER_MODELS:
        assert WHISPER_DISPLAY_TO_ID[display] == model_id
        assert WHISPER_ID_TO_DISPLAY[model_id] == display

    assert WHISPER_DISPLAY_TO_ID["large-v3 (best quality)"] == (
        "mlx-community/whisper-large-v3-mlx"
    )
    assert WHISPER_DISPLAY_TO_ID["large-v3-turbo (fast)"] == (
        "mlx-community/whisper-large-v3-turbo"
    )


def test_models_tab_backend_mappings():
    from localwhisper.settings.tabs.models import (
        BACKEND_DISPLAY_TO_KEY,
        BACKEND_KEY_TO_DISPLAY,
    )

    assert BACKEND_DISPLAY_TO_KEY["Ollama"] == "ollama"
    assert BACKEND_DISPLAY_TO_KEY["OpenAI"] == "openai"
    assert BACKEND_KEY_TO_DISPLAY["ollama"] == "Ollama"
    assert BACKEND_KEY_TO_DISPLAY["openai"] == "OpenAI"
