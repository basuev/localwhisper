"""Layer 1: settings module tests - imports and pure logic (mappings)."""

import importlib


SETTINGS_MODULES = [
    "localwhisper.settings",
    "localwhisper.settings.controls",
    "localwhisper.settings.window",
    "localwhisper.settings.tabs.general",
    "localwhisper.settings.tabs.models",
    "localwhisper.settings.tabs.audio",
    "localwhisper.settings.tabs.advanced",
]


def test_settings_modules_import():
    errors = []
    for name in SETTINGS_MODULES:
        try:
            importlib.import_module(name)
        except Exception as e:
            errors.append(f"{name}: {e}")
    assert not errors, "import errors:\n" + "\n".join(errors)


def test_controls_exports():
    from localwhisper.settings import (
        LabeledDropdown,
        LabeledSliderWithCheckbox,
        LabeledTextField,
        LabeledToggle,
        SoundPicker,
    )

    for cls in (
        LabeledDropdown,
        LabeledSliderWithCheckbox,
        LabeledTextField,
        LabeledToggle,
        SoundPicker,
    ):
        assert cls is not None


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


def test_window_constants():
    from localwhisper.settings.window import (
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        TAB_LABELS,
    )

    assert WINDOW_WIDTH > 0
    assert WINDOW_HEIGHT > 0
    assert TAB_LABELS == ["General", "Models", "Audio", "Advanced"]


def test_controls_constants():
    from localwhisper.settings.controls import (
        LABEL_WIDTH,
        CONTROL_WIDTH,
        ROW_HEIGHT,
        TOTAL_WIDTH,
    )

    assert TOTAL_WIDTH == LABEL_WIDTH + CONTROL_WIDTH
    assert ROW_HEIGHT > 0


def test_general_tab_translate_items():
    from localwhisper.constants import TRANSLATE_LANGUAGES

    assert TRANSLATE_LANGUAGES[0] == "Off"
    assert len(TRANSLATE_LANGUAGES) > 1


def test_audio_tab_system_default_constant():
    from localwhisper.settings.tabs.audio import SYSTEM_DEFAULT

    assert SYSTEM_DEFAULT == "System Default"
