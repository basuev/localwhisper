import io
import logging
import subprocess
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

log = logging.getLogger(__name__)


def _refresh_device_list():
    sd._terminate()
    sd._initialize()


def list_input_devices() -> list[dict]:
    _refresh_device_list()
    return [d for d in sd.query_devices() if d["max_input_channels"] > 0]


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
        recording_volume: int | None = 100,
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
        self._chunk_callback = None

    def _get_input_volume(self) -> int:
        result = subprocess.run(
            ["osascript", "-e", "input volume of (get volume settings)"],
            capture_output=True,
            text=True,
        )
        return int(result.stdout.strip())

    def _set_input_volume(self, volume: int):
        subprocess.run(
            ["osascript", "-e", f"set volume input volume {volume}"],
            capture_output=True,
        )

    def _find_device(self, refresh: bool = False) -> dict:
        if refresh:
            _refresh_device_list()
        if isinstance(self.input_device, int):
            return sd.query_devices(self.input_device)
        if isinstance(self.input_device, str):
            for dev in sd.query_devices():
                name_match = self.input_device.lower() in dev["name"].lower()
                if name_match and dev["max_input_channels"] > 0:
                    return dev
            raise ValueError(f"No input device matching '{self.input_device}'")
        return sd.query_devices(kind="input")

    def _try_open_stream(self, device_info: dict) -> bool:
        self._device_rate = int(device_info["default_samplerate"])
        device_index = device_info["index"]
        log.info(
            "Trying input device: %s (index=%d, rate=%d)",
            device_info["name"],
            device_index,
            self._device_rate,
        )
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

    def _apply_volume_async(self):
        try:
            self._saved_volume = self._get_input_volume()
            self._set_input_volume(self.recording_volume)
        except Exception:
            log.warning("failed to set recording volume")

    def start(self, chunk_callback=None):
        self._chunk_callback = chunk_callback
        if self.recording_volume is not None:
            threading.Thread(target=self._apply_volume_async, daemon=True).start()

        with self._lock:
            self._frames = []
            self._recording = True

        primary = self._find_device()
        if self._try_open_stream(primary):
            return

        primary = self._find_device(refresh=True)
        if self._try_open_stream(primary):
            return

        primary_index = primary["index"]
        fallbacks = [
            d
            for d in sd.query_devices()
            if d["max_input_channels"] > 0 and d["index"] != primary_index
        ]
        for dev in fallbacks:
            if self._try_open_stream(dev):
                return

        raise sd.PortAudioError("all input devices failed")

    def _callback(self, indata, frames, time, status):
        if self._recording:
            data = indata.copy()
            self._frames.append(data)
            if self._chunk_callback:
                flat = data.flatten()
                if self._device_rate != self.sample_rate:
                    flat = _resample(flat, self._device_rate, self.sample_rate)
                self._chunk_callback(flat)

    def stop_array(self) -> np.ndarray | None:
        with self._lock:
            self._recording = False

        self._stream.stop()
        self._stream.close()

        if self._saved_volume is not None:
            vol = self._saved_volume
            self._saved_volume = None
            threading.Thread(
                target=self._set_input_volume,
                args=(vol,),
                daemon=True,
            ).start()

        if not self._frames:
            log.warning("no audio frames captured")
            return None

        audio = np.concatenate(self._frames, axis=0).flatten()

        if self._device_rate != self.sample_rate:
            audio = _resample(audio, self._device_rate, self.sample_rate)

        duration = len(audio) / self.sample_rate
        if duration < self.min_recording_duration:
            log.warning(
                "recording too short: %.2fs < %.2fs",
                duration,
                self.min_recording_duration,
            )
            return None

        rms = float(np.sqrt(np.mean(audio**2)))
        if rms < self.min_audio_energy:
            log.warning("audio energy too low: %.6f < %.3f", rms, self.min_audio_energy)
            return None

        log.info(
            "recording: %.2fs, RMS=%.4f, frames=%d, device_rate=%d",
            duration,
            rms,
            len(self._frames),
            self._device_rate,
        )
        return audio

    def stop(self) -> bytes:
        audio = self.stop_array()
        if audio is None:
            return b""
        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="FLOAT")
        return buf.getvalue()
