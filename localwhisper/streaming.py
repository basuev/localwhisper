import logging
import queue
import threading

import numpy as np

log = logging.getLogger(__name__)


_SENTINEL = None


class ChunkAccumulator:
    def __init__(self, chunk_duration: float, sample_rate: int):
        self._chunk_samples = int(chunk_duration * sample_rate)
        self._buffer: list[np.ndarray] = []
        self._buffered_samples = 0

    def add_frames(self, frames: np.ndarray) -> np.ndarray | None:
        self._buffer.append(frames)
        self._buffered_samples += len(frames)

        if self._buffered_samples >= self._chunk_samples:
            chunk = np.concatenate(self._buffer)
            self._buffer = []
            self._buffered_samples = 0
            return chunk
        return None

    def flush(self) -> np.ndarray | None:
        if not self._buffer:
            return None
        chunk = np.concatenate(self._buffer)
        self._buffer = []
        self._buffered_samples = 0
        return chunk


class StreamingTranscriber:
    def __init__(self, transcriber):
        self._transcriber = transcriber
        self._queue: queue.Queue = queue.Queue()
        self._results: list[str] = []
        self._cancelled = False
        self._worker: threading.Thread | None = None

    def start(self):
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        while True:
            item = self._queue.get()
            if item is _SENTINEL or self._cancelled:
                break
            try:
                text = self._transcriber.transcribe_array(item)
                if text:
                    self._results.append(text)
            except Exception:
                log.exception("streaming chunk transcription failed")

    def submit_chunk(self, audio: np.ndarray):
        self._queue.put(audio)

    def finish(self) -> str:
        self._queue.put(_SENTINEL)
        if self._worker:
            self._worker.join(timeout=30)
        return " ".join(self._results)

    def cancel(self) -> str:
        self._cancelled = True
        self._queue.put(_SENTINEL)
        if self._worker:
            self._worker.join(timeout=5)
        return " ".join(self._results)
