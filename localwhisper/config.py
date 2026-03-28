import shutil
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "whisper_model": "mlx-community/whisper-large-v3-mlx",
    "language": "ru",
    "ollama_model": "gemma3:4b",
    "ollama_url": "http://localhost:11434",
    "hotkey_keycode": 61,
    "model_idle_timeout": 300,
    "sample_rate": 16000,
    "recording_volume": 100,
    "min_audio_energy": 0.003,
    "min_recording_duration": 0.3,
    "sound_start": "/System/Library/Sounds/Tink.aiff",
    "sound_stop": "/System/Library/Sounds/Pop.aiff",
    "sound_cancel": "/System/Library/Sounds/Funk.aiff",
    "sound_error": "/System/Library/Sounds/Sosumi.aiff",
    "input_device": None,
    "postprocessor": "ollama",
    "openai_model": "gpt-5.4",
    "translate_to": None,
    "postprocess": True,
    "streaming": True,
    "chunk_duration": 5.0,
    "blob_theme": "dark",
}

CONFIG_DIR = Path.home() / ".config" / "localwhisper"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


def load_config(config_path: Path | None = None) -> dict:
    config_path = config_path or CONFIG_PATH

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        example = Path(__file__).parent.parent / "config.example.yaml"
        if example.exists():
            shutil.copy(example, config_path)
        else:
            with open(config_path, "w") as f:
                yaml.safe_dump(
                    DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True
                )

    with open(config_path) as f:
        user_config = yaml.safe_load(f) or {}

    config = {**DEFAULT_CONFIG, **user_config}
    return config


def save_config(updates: dict, config_path: Path | None = None) -> None:
    config_path = config_path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path) as f:
        current = yaml.safe_load(f) or {}
    current.update(updates)
    with open(config_path, "w") as f:
        yaml.safe_dump(current, f, default_flow_style=False, allow_unicode=True)
