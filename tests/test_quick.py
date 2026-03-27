"""Layer 0: Quick checks - imports and config completeness."""

import importlib

from localwhisper.constants import OLLAMA_MODELS

MODULES = [
    "localwhisper.config",
    "localwhisper.history",
    "localwhisper.postprocessor",
    "localwhisper.transcriber",
    "localwhisper.recorder",
    "localwhisper.sounds",
    "localwhisper.clipboard",
    "localwhisper.hotkey",
    "localwhisper.preflight",
    "localwhisper.events",
    "localwhisper.engine",
    "localwhisper.streaming",
    "localwhisper.constants",
    "localwhisper.app",
    "localwhisper.settings",
    "localwhisper.settings.controls",
    "localwhisper.settings.window",
    "localwhisper.settings.tabs.general",
    "localwhisper.settings.tabs.models",
    "localwhisper.settings.tabs.audio",
    "localwhisper.settings.tabs.advanced",
]

REQUIRED_CONFIG_KEYS = [
    "whisper_model",
    "language",
    "ollama_model",
    "ollama_url",
    "postprocess_prompt",
    "hotkey_keycode",
    "model_idle_timeout",
    "sample_rate",
    "recording_volume",
    "min_audio_energy",
    "min_recording_duration",
    "sound_start",
    "sound_stop",
    "sound_cancel",
    "postprocess",
    "streaming",
    "chunk_duration",
]


def test_all_modules_import():
    errors = []
    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"{module_name}: {e}")
    assert not errors, "Import errors:\n" + "\n".join(errors)


def test_default_config_has_all_keys(default_config):
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in default_config]
    assert not missing, f"Missing config keys: {missing}"


def test_entry_point_resolves():
    mod = importlib.import_module("localwhisper.app")
    assert hasattr(mod, "main"), "localwhisper.app must have main()"
    assert callable(mod.main)


def test_ollama_models_constant_exists():
    assert len(OLLAMA_MODELS) >= 1
    ids = [model_id for model_id, _ in OLLAMA_MODELS]
    assert "gemma3:4b" in ids


def test_default_ollama_model_is_gemma(default_config):
    assert default_config["ollama_model"] == "gemma3:4b"
