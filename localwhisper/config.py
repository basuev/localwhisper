import shutil
import tempfile
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
    "sound_feedback": "/System/Library/Sounds/Glass.aiff",
    "input_device": None,
    "postprocessor": "ollama",
    "openai_model": "gpt-5.4",
    "translate_to": None,
    "postprocess": True,
    "streaming": True,
    "chunk_duration": 5.0,
    "blob_theme": "dark",
    "feedback_double_click_timeout": 300,
    "dictionary_similarity_threshold": 0.4,
}

CONFIG_DIR = Path.home() / ".config" / "localwhisper"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


def _write_config(config_path: Path, data: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config_path.parent, suffix=".yaml.tmp")
    try:
        with open(fd, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        Path(tmp).replace(config_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_config(config_path: Path | None = None) -> dict:
    config_path = config_path or CONFIG_PATH

    if not config_path.exists():
        example = Path(__file__).parent.parent / "config.example.yaml"
        if example.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(example, config_path)
        else:
            _write_config(config_path, DEFAULT_CONFIG)

    with open(config_path) as f:
        user_config = yaml.safe_load(f) or {}

    if not user_config and config_path.stat().st_size == 0:
        _write_config(config_path, DEFAULT_CONFIG)
        user_config = dict(DEFAULT_CONFIG)

    config = {**DEFAULT_CONFIG, **user_config}
    return config


def save_config(updates: dict, config_path: Path | None = None) -> None:
    config_path = config_path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path) as f:
        current = yaml.safe_load(f) or {}
    current.update(updates)
    _write_config(config_path, current)
