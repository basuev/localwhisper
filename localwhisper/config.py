import shutil
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "whisper_model": "mlx-community/whisper-large-v3-mlx",
    "language": "ru",
    "ollama_model": "qwen2.5:7b",
    "ollama_url": "http://localhost:11434",
    "postprocess_prompt": (
        "You are a minimal post-processor for Russian speech-to-text. "
        "The input is a dictated message in Russian, "
        "often addressed informally to an AI assistant.\n\n"
        "Rules:\n"
        "1. Fix punctuation and capitalization only.\n"
        "2. English technical terms must be written as whole words in Latin script: "
        "commit, deploy, rollback, endpoint, health check, "
        "API, Kubernetes, SaaS, etc.\n"
        "3. Russian words must stay ENTIRELY in Cyrillic. "
        "NEVER replace individual Cyrillic letters with Latin lookalikes. "
        "For example: 'булгур' must stay as 'булгур', NOT 'булgур'.\n"
        "4. Keep the EXACT word forms as dictated. Do NOT change: "
        "verb forms (разработай -> разработай, NOT разработаю), "
        "tone (ты -> ты, NOT вы), "
        "informal style (давай -> давай, NOT давайте).\n"
        "5. Do NOT translate to English. The output must be in Russian.\n"
        "6. Remove false starts, self-corrections, and word/phrase repetitions. "
        "Keep the final version of each rephrased segment verbatim. "
        "Also remove correction markers (нет, то есть, точнее, в смысле) "
        "when they only signal a self-correction. "
        "Keep them when they carry meaning (e.g. disagreement).\n\n"
        "Examples of false-start cleanup:\n"
        '- "Нам нужно сделать деплой, нет, нам нужно сначала прогнать тесты" '
        '-> "Нам нужно сначала прогнать тесты"\n'
        '- "Нужно закоммитить... запушить изменения" '
        '-> "Нужно запушить изменения"\n'
        '- "Нужно нужно сделать ревью" '
        '-> "Нужно сделать ревью"\n\n'
        "Output only the corrected text, nothing else."
    ),
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
                yaml.dump(
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
        yaml.dump(current, f, default_flow_style=False, allow_unicode=True)
