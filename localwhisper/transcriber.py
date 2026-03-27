import io
import logging
import threading
import time

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

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
            self._model_loaded = True

    def cancel_unload_timer(self):
        if self._unload_timer:
            self._unload_timer.cancel()
            self._unload_timer = None

    def _schedule_unload(self):
        if self._unload_timer:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(self.idle_timeout, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def preload(self):
        from .preflight import is_model_cached

        if not is_model_cached(self.model_name):
            log.warning(
                "Whisper model not cached, skipping preload: %s",
                self.model_name,
            )
            return

        with self._lock:
            self._ensure_loaded()

        silence = np.zeros(16000, dtype=np.float32)
        try:
            self._mlx_whisper.transcribe(
                silence,
                path_or_hf_repo=self.model_name,
                language=self.language,
            )
            log.info("whisper model preloaded: %s", self.model_name)
        except Exception:
            log.warning("failed to preload whisper model", exc_info=True)

        self._last_used = time.time()
        self._schedule_unload()

    def _unload(self):
        with self._lock:
            if self._model_loaded:
                self._mlx_whisper = None
                self._model_loaded = False
                import gc

                gc.collect()

    def transcribe_array(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""

        from .preflight import is_model_cached

        if not is_model_cached(self.model_name):
            log.warning("model not cached, skipping transcription: %s", self.model_name)
            return ""

        with self._lock:
            self._ensure_loaded()
            self._last_used = time.time()

        result = self._mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model_name,
            language=self.language,
        )
        text = result.get("text", "").strip()

        self._schedule_unload()

        if _is_hallucination(text):
            return ""

        return text

    def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""

        buf = io.BytesIO(audio_data)
        audio, _ = sf.read(buf, dtype="float32")
        return self.transcribe_array(audio)
