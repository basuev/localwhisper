import io
import logging
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

log = logging.getLogger(__name__)


def _resample(audio: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    if orig_rate == target_rate:
        return audio
    ratio = target_rate / orig_rate
    n_samples = int(len(audio) * ratio)
    indices = np.arange(n_samples) / ratio
    indices_floor = np.floor(indices).astype(int)
    indices_ceil = np.minimum(indices_floor + 1, len(audio) - 1)
    frac = indices - indices_floor
    return audio[indices_floor] * (1 - frac) + audio[indices_ceil] * frac


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        recording_volume: int = 100,
        min_audio_energy: float = 0.003,
        min_recording_duration: float = 0.3,
        input_device: str | int | None = None,
    ):
        self.sample_rate = sample_rate
        self.recording_volume = recording_volume
        self.min_audio_energy = min_audio_energy
        self.min_recording_duration = min_recording_duration
        self.input_device = input_device
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._saved_volume: int | None = None
        self._device_rate: int = sample_rate

    def _get_input_volume(self) -> int:
        result = subprocess.run(
            ["osascript", "-e", "input volume of (get volume settings)"],
            capture_output=True, text=True,
        )
        return int(result.stdout.strip())

    def _set_input_volume(self, volume: int):
        subprocess.run(
            ["osascript", "-e", f"set volume input volume {volume}"],
            capture_output=True,
        )

    def _find_device(self) -> dict:
        if isinstance(self.input_device, int):
            return sd.query_devices(self.input_device)
        if isinstance(self.input_device, str):
            for dev in sd.query_devices():
                if self.input_device.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
                    return dev
            raise ValueError(f"No input device matching '{self.input_device}'")
        return sd.query_devices(kind="input")

    def _try_open_stream(self, device_info: dict) -> bool:
        self._device_rate = int(device_info["default_samplerate"])
        device_index = device_info["index"]
        log.info("Trying input device: %s (index=%d, rate=%d)",
                 device_info["name"], device_index, self._device_rate)
        try:
            self._stream = sd.InputStream(
                device=device_index,
                samplerate=self._device_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            log.info("Opened input device: %s", device_info["name"])
            return True
        except sd.PortAudioError as e:
            log.warning("Failed to open device '%s': %s", device_info["name"], e)
            return False

    def start(self):
        self._saved_volume = self._get_input_volume()
        self._set_input_volume(self.recording_volume)

        with self._lock:
            self._frames = []
            self._recording = True

        primary = self._find_device()
        if self._try_open_stream(primary):
            return

        primary_index = primary["index"]
        fallbacks = [
            d for d in sd.query_devices()
            if d["max_input_channels"] > 0 and d["index"] != primary_index
        ]
        for dev in fallbacks:
            if self._try_open_stream(dev):
                return

        raise sd.PortAudioError("All input devices failed")

    def _callback(self, indata, frames, time, status):
        if self._recording:
            self._frames.append(indata.copy())

    def stop(self) -> bytes:
        with self._lock:
            self._recording = False

        self._stream.stop()
        self._stream.close()

        if self._saved_volume is not None:
            self._set_input_volume(self._saved_volume)
            self._saved_volume = None

        if not self._frames:
            log.warning("No audio frames captured")
            return b""

        audio = np.concatenate(self._frames, axis=0).flatten()

        if self._device_rate != self.sample_rate:
            audio = _resample(audio, self._device_rate, self.sample_rate)

        duration = len(audio) / self.sample_rate
        if duration < self.min_recording_duration:
            log.warning("Recording too short: %.2fs < %.2fs", duration, self.min_recording_duration)
            return b""

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < self.min_audio_energy:
            log.warning("Audio energy too low: %.6f < %.3f", rms, self.min_audio_energy)
            return b""

        log.info("Recording: %.2fs, RMS=%.4f, frames=%d, device_rate=%d", duration, rms, len(self._frames), self._device_rate)

        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="FLOAT")
        return buf.getvalue()
