import importlib

import yaml

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
    assert not errors, "import errors:\n" + "\n".join(errors)


def test_default_config_has_all_keys(default_config):
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in default_config]
    assert not missing, f"missing config keys: {missing}"


def test_entry_point_resolves():
    mod = importlib.import_module("localwhisper.app")
    assert hasattr(mod, "main")
    assert callable(mod.main)


def test_load_config_defaults(tmp_path, default_config):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}\n")

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    for key, value in default_config.items():
        assert key in config
        assert config[key] == value


def test_load_config_partial_override(tmp_path, default_config):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "en"}))

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config["language"] == "en"
    assert config["whisper_model"] == default_config["whisper_model"]


def test_load_config_creates_file(tmp_path):
    config_file = tmp_path / "sub" / "config.yaml"

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config_file.exists()
    assert "whisper_model" in config


def test_save_config_roundtrip(tmp_path):
    from localwhisper.config import load_config, save_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "ru"}))

    save_config({"language": "en", "translate_to": "German"}, config_path=config_file)

    config = load_config(config_path=config_file)
    assert config["language"] == "en"
    assert config["translate_to"] == "German"


def test_save_config_preserves_existing_keys(tmp_path):
    from localwhisper.config import save_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "ru", "ollama_model": "gemma3:4b"}))

    save_config({"language": "en"}, config_path=config_file)

    with open(config_file) as f:
        saved = yaml.safe_load(f)
    assert saved["language"] == "en"
    assert saved["ollama_model"] == "gemma3:4b"
