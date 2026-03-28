import logging
import threading
from collections import defaultdict

import numpy as np

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
from .postprocessor import PostProcessor
from .recorder import AudioRecorder
from .streaming import ChunkAccumulator, StreamingTranscriber
from .transcriber import Transcriber

RMS_FULL_SCALE = 0.1

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
        self._streaming_transcriber = None
        self._chunk_accumulator = None
        self._amplitude_callback = None

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

    def set_amplitude_callback(self, callback) -> None:
        self._amplitude_callback = callback

    def off(self, event_type: type, callback) -> None:
        import contextlib

        with contextlib.suppress(ValueError):
            self._listeners[event_type].remove(callback)

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
            if self._streaming_transcriber:
                self._streaming_transcriber.cancel()
                self._streaming_transcriber = None
                self._chunk_accumulator = None
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
            target=self._process,
            args=(audio_data,),
            daemon=True,
        )
        self._processing_thread.start()

    def _start_recording(self):
        self._cancelled = False
        streaming = self._config.get("streaming", False)

        chunk_callback = None
        if streaming:
            self._transcriber.cancel_unload_timer()
            self._chunk_accumulator = ChunkAccumulator(
                chunk_duration=self._config.get("chunk_duration", 5.0),
                sample_rate=self._config["sample_rate"],
            )
            self._streaming_transcriber = StreamingTranscriber(self._transcriber)
            self._streaming_transcriber.start()

            acc = self._chunk_accumulator
            st = self._streaming_transcriber

            def chunk_callback(frames):
                chunk = acc.add_frames(frames)
                if chunk is not None:
                    st.submit_chunk(chunk)

        amplitude_cb = self._amplitude_callback
        inner_cb = chunk_callback

        if inner_cb or amplitude_cb:

            def chunk_callback(frames):
                if inner_cb:
                    inner_cb(frames)
                if amplitude_cb:
                    rms = float(np.sqrt(np.mean(frames**2)))
                    amplitude_cb(min(rms / RMS_FULL_SCALE, 1.0))

        try:
            self._recorder.start(chunk_callback=chunk_callback)
        except Exception:
            log.exception("failed to start recording")
            if self._streaming_transcriber:
                self._streaming_transcriber.cancel()
                self._streaming_transcriber = None
                self._chunk_accumulator = None
            self._emit(RecordingFailed(reason="device_error"))
            return
        self._state = "recording"
        self._emit(RecordingStarted())

    def _stop_recording(self):
        audio = self._recorder.stop_array()

        if self._streaming_transcriber:
            st = self._streaming_transcriber
            acc = self._chunk_accumulator
            self._streaming_transcriber = None
            self._chunk_accumulator = None

            remainder = acc.flush() if acc else None
            if remainder is not None:
                st.submit_chunk(remainder)

            duration = (
                len(audio) / self._config["sample_rate"] if audio is not None else 0.0
            )
            self._state = "processing"
            self._emit(RecordingDone(audio_data=b"", duration=duration))

            self._processing_thread = threading.Thread(
                target=self._process_streaming,
                args=(st,),
                daemon=True,
            )
            self._processing_thread.start()
            return

        if audio is None:
            self._state = "idle"
            self._emit(RecordingFailed(reason="no_audio"))
            return

        duration = len(audio) / self._config["sample_rate"]

        self._state = "processing"
        self._emit(RecordingDone(audio_data=b"", duration=duration))

        self._processing_thread = threading.Thread(
            target=self._process_array,
            args=(audio,),
            daemon=True,
        )
        self._processing_thread.start()

    def _finish_with_text(self, raw_text):
        self._emit(TranscriptionDone(raw_text=raw_text))

        if not raw_text:
            return

        if not self._config.get("postprocess", True):
            self._emit(
                PostProcessingDone(
                    raw_text=raw_text,
                    processed_text=raw_text,
                )
            )
            return

        self._emit(PostProcessingStarted())
        try:

            def cancel_check():
                return self._cancelled

            processed_text = self._postprocessor.process(
                raw_text, cancel_check=cancel_check
            )
            self._emit(
                PostProcessingDone(
                    raw_text=raw_text,
                    processed_text=processed_text,
                )
            )
        except Exception as exc:
            self._emit(
                PostProcessingFailed(
                    raw_text=raw_text,
                    error=str(exc),
                )
            )

    def _process_streaming(self, streaming_transcriber):
        try:
            if self._cancelled:
                streaming_transcriber.cancel()
                return

            self._emit(TranscriptionStarted())
            raw_text = streaming_transcriber.finish()

            if self._cancelled:
                return

            self._finish_with_text(raw_text)
        finally:
            with self._state_lock:
                if self._state == "processing":
                    self._state = "idle"
                self._cancelled = False

    def _process_array(self, audio):
        try:
            if self._cancelled:
                return

            self._emit(TranscriptionStarted())
            try:
                raw_text = self._transcriber.transcribe_array(audio)
            except Exception as exc:
                self._emit(TranscriptionFailed(error=str(exc)))
                return

            if self._cancelled:
                return

            self._finish_with_text(raw_text)
        finally:
            with self._state_lock:
                if self._state == "processing":
                    self._state = "idle"
                self._cancelled = False

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

            self._finish_with_text(raw_text)
        finally:
            with self._state_lock:
                if self._state == "processing":
                    self._state = "idle"
                self._cancelled = False

    def update_config(self, updates: dict) -> None:
        self._config.update(updates)
        if "input_device" in updates:
            self._recorder.input_device = updates["input_device"]
        if "language" in updates:
            self._transcriber.language = updates["language"]
        if "whisper_model" in updates:
            self._transcriber.model_name = updates["whisper_model"]
            self._transcriber._unload()
        if "model_idle_timeout" in updates:
            self._transcriber.idle_timeout = updates["model_idle_timeout"]
        if "translate_to" in updates:
            self._postprocessor.set_translate_to(updates.get("translate_to"))
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
