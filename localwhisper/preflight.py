import importlib.util
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _notify(message: str):
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{safe}" with title "LocalWhisper"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _check_imports() -> bool:
    missing = []
    for mod in ["mlx_whisper", "sounddevice", "rumps", "numpy", "soundfile"]:
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)

    if missing:
        msg = f"Missing packages: {', '.join(missing)}. Run install.sh"
        log.error(msg)
        _notify(msg)
        return False
    return True


def is_model_cached(model_repo: str) -> bool:
    from huggingface_hub.constants import HF_HUB_CACHE

    cache_name = "models--" + model_repo.replace("/", "--")
    snapshots = Path(HF_HUB_CACHE) / cache_name / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def _check_whisper_model(model_repo: str) -> bool:
    if not is_model_cached(model_repo):
        msg = f"Whisper model not downloaded: {model_repo}. Run install.sh"
        log.error(msg)
        _notify(msg)
        return False
    return True


def run_checks(config: dict) -> bool:
    if not _check_imports():
        return False

    return _check_whisper_model(config["whisper_model"])
