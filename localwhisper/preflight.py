import importlib.util
import logging
import subprocess
from pathlib import Path

from .paths import is_bundled_app

log = logging.getLogger(__name__)


def notify(message: str):
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{safe}" with title "localwhisper"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _install_hint() -> str:
    if is_bundled_app():
        return "Reinstall localwhisper via Homebrew Cask."
    return "Run uv sync."


def _check_imports() -> bool:
    missing = []
    for mod in ["mlx_whisper", "sounddevice", "rumps", "numpy", "soundfile"]:
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)

    if missing:
        msg = f"Missing packages: {', '.join(missing)}. {_install_hint()}"
        log.error(msg)
        notify(msg)
        return False
    return True


def is_model_cached(model_repo: str) -> bool:
    from huggingface_hub.constants import HF_HUB_CACHE

    cache_name = "models--" + model_repo.replace("/", "--")
    snapshots = Path(HF_HUB_CACHE) / cache_name / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def _check_whisper_model(model_repo: str) -> bool:
    if not is_model_cached(model_repo):
        msg = f"Whisper model not downloaded yet: {model_repo}."
        log.error(msg)
        notify(msg)
        return False
    return True


def run_checks(config: dict) -> bool:
    return _check_imports()
