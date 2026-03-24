import io
import logging
import threading
from collections import defaultdict

import soundfile as sf

from .events import (
    Cancelled,
    PostProcessingDone,
    PostProcessingFailed,
    PostProcessingStarted,
    RecordingDone,
    RecordingFailed,
    RecordingStarted,
    TranscriptionDone,
    TranscriptionFailed,
    TranscriptionStarted,
)
from .recorder import AudioRecorder
from .transcriber import Transcriber
from .postprocessor import PostProcessor

log = logging.getLogger(__name__)


class LocalWhisperEngine:
    def __init__(self, config: dict):
        self._config = dict(config)
        self._listeners = defaultdict(list)
        self._state = "idle"
        self._state_lock = threading.Lock()
        self._cancelled = False
        self._shutdown = False
        self._processing_thread = None

        self._recorder = AudioRecorder(
            sample_rate=config["sample_rate"],
            recording_volume=config["recording_volume"],
            min_audio_energy=config["min_audio_energy"],
            min_recording_duration=config["min_recording_duration"],
            input_device=config["input_device"],
        )
        self._transcriber = Transcriber(config)
        self._postprocessor = PostProcessor(config)

    @property
    def state(self) -> str:
        return self._state

    def on(self, event_type: type, callback) -> None:
        self._listeners[event_type].append(callback)

    def off(self, event_type: type, callback) -> None:
        try:
            self._listeners[event_type].remove(callback)
        except ValueError:
            pass

    def _emit(self, event) -> None:
        for cb in list(self._listeners.get(type(event), [])):
            try:
                cb(event)
            except Exception:
                log.exception("error in event callback")

    def toggle(self) -> None:
        with self._state_lock:
            if self._shutdown:
                return
            if self._state == "idle":
                self._start_recording()
            elif self._state == "recording":
                self._stop_recording()

    def cancel(self) -> None:
        with self._state_lock:
            if self._shutdown:
                return
            prev = self._state
            if prev == "recording":
                self._state = "idle"
            elif prev == "processing":
                self._cancelled = True
                self._state = "idle"
            else:
                return

        if prev == "recording":
            self._recorder.stop()
            self._emit(Cancelled(stage="recording"))
        elif prev == "processing":
            self._emit(Cancelled(stage="processing"))

    def transcribe(self, audio_data: bytes) -> None:
        with self._state_lock:
            if self._shutdown or self._state != "idle":
                return
            self._state = "processing"
            self._cancelled = False

        self._processing_thread = threading.Thread(
            target=self._process, args=(audio_data,), daemon=True,
        )
        self._processing_thread.start()

    def _start_recording(self):
        self._cancelled = False
        try:
            self._recorder.start()
        except Exception:
            log.exception("failed to start recording")
            self._emit(RecordingFailed(reason="device_error"))
            return
        self._state = "recording"
        self._emit(RecordingStarted())

    def _stop_recording(self):
        audio_data = self._recorder.stop()
        if not audio_data:
            self._state = "idle"
            self._emit(RecordingFailed(reason="no_audio"))
            return

        with io.BytesIO(audio_data) as buf:
            info = sf.info(buf)
            duration = info.duration

        self._state = "processing"
        self._emit(RecordingDone(audio_data=audio_data, duration=duration))

        self._processing_thread = threading.Thread(
            target=self._process, args=(audio_data,), daemon=True,
        )
        self._processing_thread.start()

    def _process(self, audio_data: bytes):
        try:
            if self._cancelled:
                return

            self._emit(TranscriptionStarted())
            try:
                raw_text = self._transcriber.transcribe(audio_data)
            except Exception as exc:
                self._emit(TranscriptionFailed(error=str(exc)))
                return

            if self._cancelled:
                return

            self._emit(TranscriptionDone(raw_text=raw_text))

            if not raw_text:
                return

            self._emit(PostProcessingStarted())
            try:
                processed_text = self._postprocessor.process(raw_text)
                self._emit(PostProcessingDone(
                    raw_text=raw_text, processed_text=processed_text,
                ))
            except Exception as exc:
                self._emit(PostProcessingFailed(
                    raw_text=raw_text, error=str(exc),
                ))
        finally:
            with self._state_lock:
                if self._state == "processing":
                    self._state = "idle"
                self._cancelled = False

    def update_config(self, updates: dict) -> None:
        self._config.update(updates)
        if "language" in updates:
            self._transcriber.language = updates["language"]
        if "model_idle_timeout" in updates:
            self._transcriber.idle_timeout = updates["model_idle_timeout"]
        if "translate_to" in updates:
            self._postprocessor.set_translate_to(updates.get("translate_to"))
        if "postprocess_prompt" in updates:
            self._postprocessor.prompt = updates["postprocess_prompt"]
        if "ollama_url" in updates:
            self._postprocessor.ollama_url = updates["ollama_url"]
        pp_keys = {"postprocessor", "ollama_model", "openai_model"}
        if pp_keys & set(updates):
            backend = self._config.get("postprocessor", "ollama")
            if backend == "openai":
                model = self._config.get("openai_model", "gpt-5.4")
            else:
                model = self._config["ollama_model"]
            self._postprocessor.switch(backend, model)

    def shutdown(self) -> None:
        self.cancel()
        with self._state_lock:
            self._shutdown = True
        self._transcriber._unload()
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
