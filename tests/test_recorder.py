import numpy as np


def _make_recorder(**overrides):
    from localwhisper.recorder import AudioRecorder

    defaults = {
        "sample_rate": 16000,
        "min_audio_energy": 0.003,
        "min_recording_duration": 0.3,
    }
    defaults.update(overrides)
    return AudioRecorder(**defaults)


def _make_sine(duration=1.0, sample_rate=16000):
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)


def _setup_for_stop(rec, frames):
    rec._frames = [frames]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None


def test_recorder_rejects_silence():
    rec = _make_recorder()
    _setup_for_stop(rec, np.zeros((8000, 1), dtype=np.float32))
    assert rec.stop() == b""


def test_recorder_accepts_speech():
    rec = _make_recorder()
    _setup_for_stop(rec, _make_sine())
    result = rec.stop()
    assert len(result) > 0


def test_recorder_rejects_short_duration():
    rec = _make_recorder()
    _setup_for_stop(rec, _make_sine(duration=0.1))
    assert rec.stop() == b""


def test_recorder_stop_array_returns_numpy():
    rec = _make_recorder()
    _setup_for_stop(rec, _make_sine())
    result = rec.stop_array()
    assert isinstance(result, np.ndarray)
    assert len(result) == 16000


def test_recorder_stop_array_returns_none_on_silence():
    rec = _make_recorder()
    _setup_for_stop(rec, np.zeros((8000, 1), dtype=np.float32))
    assert rec.stop_array() is None


def test_refresh_device_list_reinitializes(monkeypatch):
    from unittest.mock import Mock

    import sounddevice as sd

    from localwhisper.recorder import _refresh_device_list

    mock_term = Mock()
    mock_init = Mock()
    monkeypatch.setattr(sd, "_terminate", mock_term)
    monkeypatch.setattr(sd, "_initialize", mock_init)

    _refresh_device_list()
    mock_term.assert_called_once()
    mock_init.assert_called_once()


def test_list_input_devices_filters_output_devices(monkeypatch):
    from unittest.mock import Mock

    import sounddevice as sd

    from localwhisper.recorder import list_input_devices

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())
    monkeypatch.setattr(
        sd,
        "query_devices",
        lambda: [
            {"name": "mic", "max_input_channels": 1, "index": 0},
            {"name": "speakers", "max_input_channels": 0, "index": 1},
            {"name": "headset", "max_input_channels": 2, "index": 2},
        ],
    )

    devices = list_input_devices()
    assert len(devices) == 2
    assert devices[0]["name"] == "mic"
    assert devices[1]["name"] == "headset"


def test_recorder_start_skips_volume_when_none(monkeypatch):
    from unittest.mock import Mock, patch

    import sounddevice as sd

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = _make_recorder(recording_volume=None)

    mock_device = {
        "name": "test mic",
        "index": 0,
        "max_input_channels": 1,
        "default_samplerate": 16000.0,
    }
    monkeypatch.setattr(sd, "query_devices", lambda kind=None: mock_device)

    with (
        patch.object(rec, "_get_input_volume") as mock_get,
        patch.object(rec, "_set_input_volume") as mock_set,
        patch("sounddevice.InputStream") as mock_stream,
    ):
        mock_stream.return_value.start = Mock()
        rec.start()
        mock_get.assert_not_called()
        mock_set.assert_not_called()


def test_recorder_volume_restore_non_blocking():
    import time
    from unittest.mock import patch

    rec = _make_recorder(recording_volume=100)
    _setup_for_stop(rec, _make_sine())
    rec._saved_volume = 75

    calls = []

    def fake_set_volume(vol):
        calls.append(("set", vol))

    with patch.object(rec, "_set_input_volume", side_effect=fake_set_volume):
        result = rec.stop_array()

    assert result is not None
    time.sleep(0.1)
    assert ("set", 75) in calls


def test_recorder_start_no_device_refresh(monkeypatch):
    from unittest.mock import Mock, patch

    import sounddevice as sd

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = _make_recorder(recording_volume=None)

    mock_device = {
        "name": "test mic",
        "index": 0,
        "max_input_channels": 1,
        "default_samplerate": 16000.0,
    }
    monkeypatch.setattr(sd, "query_devices", lambda **kw: mock_device)

    with patch("sounddevice.InputStream") as mock_stream:
        mock_stream.return_value.start = Mock()
        rec.start()

    sd._terminate.assert_not_called()
    sd._initialize.assert_not_called()


def test_recorder_volume_set_async_on_start(monkeypatch):
    import time
    from unittest.mock import Mock, patch

    import sounddevice as sd

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = _make_recorder(recording_volume=100)

    mock_device = {
        "name": "test mic",
        "index": 0,
        "max_input_channels": 1,
        "default_samplerate": 16000.0,
    }
    monkeypatch.setattr(sd, "query_devices", lambda **kw: mock_device)

    volume_calls = []

    def track_set(vol):
        volume_calls.append(vol)

    def track_get():
        return 50

    with (
        patch.object(rec, "_get_input_volume", side_effect=track_get),
        patch.object(rec, "_set_input_volume", side_effect=track_set),
        patch("sounddevice.InputStream") as mock_stream,
    ):
        mock_stream.return_value.start = Mock()
        rec.start()

    time.sleep(0.2)
    assert rec._saved_volume == 50
    assert 100 in volume_calls
