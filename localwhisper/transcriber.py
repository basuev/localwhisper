import tempfile
import threading
import time
from pathlib import Path

WHISPER_HALLUCINATIONS = [
    "продолжение следует",
    "субтитры делал",
    "субтитры сделал",
    "подписывайтесь на канал",
    "подпишись на канал",
    "благодарю за просмотр",
    "спасибо за просмотр",
    "спасибо за внимание",
    "редактор субтитров",
    "amara.org",
]


def _is_hallucination(text: str) -> bool:
    lower = text.lower()
    return any(h in lower for h in WHISPER_HALLUCINATIONS)


class Transcriber:
    def __init__(self, config: dict):
        self.model_name = config["whisper_model"]
        self.language = config["language"]
        self.idle_timeout = config["model_idle_timeout"]
        self._model_loaded = False
        self._last_used = 0.0
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None

    def _ensure_loaded(self):
        if not self._model_loaded:
            import mlx_whisper
            self._mlx_whisper = mlx_whisper
            # Warm up by loading the model (first transcribe call downloads/loads it)
            self._model_loaded = True

    def _schedule_unload(self):
        if self._unload_timer:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(self.idle_timeout, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _unload(self):
        with self._lock:
            if self._model_loaded:
                # Clear references to free memory
                self._mlx_whisper = None
                self._model_loaded = False
                import gc
                gc.collect()

    def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""

        with self._lock:
            self._ensure_loaded()
            self._last_used = time.time()

        # Write audio to temp file for mlx_whisper
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name

        try:
            result = self._mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=self.model_name,
                language=self.language,
            )
            text = result.get("text", "").strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self._schedule_unload()

        if _is_hallucination(text):
            return ""

        return text
