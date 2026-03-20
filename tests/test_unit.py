"""Layer 1: Unit tests - pure logic without external services."""

import io
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml


def test_load_config_defaults(tmp_path, default_config):
    """Empty YAML file -> all defaults present."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}\n")

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    for key, value in default_config.items():
        assert key in config
        assert config[key] == value


def test_load_config_partial_override(tmp_path, default_config):
    """User overrides one key, rest stay default."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "en"}))

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config["language"] == "en"
    assert config["whisper_model"] == default_config["whisper_model"]


def test_load_config_creates_file(tmp_path):
    """If config file doesn't exist, it gets created."""
    config_file = tmp_path / "sub" / "config.yaml"

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config_file.exists()
    assert "whisper_model" in config


def test_save_to_history_writes_jsonl(tmp_path):
    """History entry is valid JSONL with required fields."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("raw text", "processed text", history_path=history_file)

    lines = history_file.read_text().strip().split("\n")
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert "timestamp" in entry
    assert entry["raw"] == "raw text"
    assert entry["processed"] == "processed text"


def test_save_to_history_appends(tmp_path):
    """Each call appends exactly one line."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("a", "b", history_path=history_file)
    save_to_history("c", "d", history_path=history_file)

    lines = history_file.read_text().strip().split("\n")
    assert len(lines) == 2


def test_save_to_history_russian_text(tmp_path):
    """Russian text survives round-trip."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("привет мир", "Привет, мир.", history_path=history_file)

    entry = json.loads(history_file.read_text().strip())
    assert entry["raw"] == "привет мир"
    assert entry["processed"] == "Привет, мир."


def test_load_config_feedback_enabled_default(tmp_path):
    """feedback_enabled is present in defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}\n")

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config["feedback_enabled"] is True


def test_load_config_feedback_enabled_override(tmp_path):
    """User can override feedback_enabled to false."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"feedback_enabled": False}))

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert config["feedback_enabled"] is False


def test_save_to_history_with_rating_and_comment(tmp_path):
    """History entry includes rating and comment when provided."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("raw", "processed", rating=True, comment=None, history_path=history_file)

    entry = json.loads(history_file.read_text().strip())
    assert entry["rating"] is True
    assert entry["comment"] is None


def test_save_to_history_thumbs_down_with_comment(tmp_path):
    """Thumbs down with comment stored correctly."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("raw", "processed", rating=False, comment="bad quality", history_path=history_file)

    entry = json.loads(history_file.read_text().strip())
    assert entry["rating"] is False
    assert entry["comment"] == "bad quality"


def test_save_to_history_without_rating_comment(tmp_path):
    """Backward compat: no rating/comment -> both null in JSONL."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("raw", "processed", history_path=history_file)

    entry = json.loads(history_file.read_text().strip())
    assert entry["raw"] == "raw"
    assert entry["processed"] == "processed"
    assert entry["rating"] is None
    assert entry["comment"] is None


def test_save_to_history_all_rating_values(tmp_path):
    """All three rating values (true, false, null) are stored correctly."""
    history_file = tmp_path / "history.jsonl"

    from localwhisper.history import save_to_history

    save_to_history("a", "b", rating=True, history_path=history_file)
    save_to_history("c", "d", rating=False, history_path=history_file)
    save_to_history("e", "f", rating=None, history_path=history_file)

    lines = history_file.read_text().strip().split("\n")
    entries = [json.loads(line) for line in lines]
    assert entries[0]["rating"] is True
    assert entries[1]["rating"] is False
    assert entries[2]["rating"] is None


def test_postprocessor_empty_text(default_config):
    """Empty text returns empty without HTTP call."""
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.process("") == ""


def test_transcriber_empty_audio(default_config):
    """Empty bytes returns empty string without loading model."""
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.transcribe(b"") == ""
    assert not t._model_loaded


def test_transcriber_unload(default_config):
    """_unload resets model state."""
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    t._model_loaded = True
    t._mlx_whisper = "fake"
    t._unload()
    assert not t._model_loaded
    assert t._mlx_whisper is None


def test_recorder_rejects_silence():
    """Silent audio (near-zero RMS) returns empty bytes."""
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(sample_rate=16000, min_audio_energy=0.003, min_recording_duration=0.3)
    rec._frames = [np.zeros((8000, 1), dtype=np.float32)]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    assert rec.stop() == b""


def test_recorder_accepts_speech():
    """Audio with sufficient energy returns non-empty WAV bytes."""
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(sample_rate=16000, min_audio_energy=0.003, min_recording_duration=0.3)
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)
    rec._frames = [sine]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    result = rec.stop()
    assert len(result) > 0


def test_recorder_rejects_short_duration():
    """Very short recording (< min_recording_duration) returns empty bytes."""
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(sample_rate=16000, min_audio_energy=0.003, min_recording_duration=0.3)
    t = np.linspace(0, 0.1, 1600, dtype=np.float32)
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)
    rec._frames = [sine]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    assert rec.stop() == b""


def test_hallucination_filtered():
    """Known Whisper hallucinations are filtered out."""
    from localwhisper.transcriber import _is_hallucination

    hallucinations = [
        "Продолжение следует...",
        "Субтитры делал кто-то",
        "Подписывайтесь на канал!",
        "Спасибо за просмотр.",
        "amara.org",
    ]
    for text in hallucinations:
        assert _is_hallucination(text), f"Should filter: {text!r}"


def test_normal_text_passes_filter():
    """Normal Russian text is not filtered."""
    from localwhisper.transcriber import _is_hallucination

    normal = [
        "Привет, как дела?",
        "Напиши мне функцию для сортировки",
        "Сделай deploy на продакшен",
    ]
    for text in normal:
        assert not _is_hallucination(text), f"Should pass: {text!r}"


def test_wav_encoding_roundtrip():
    """numpy -> WAV bytes -> numpy round-trip preserves data shape."""
    sample_rate = 16000
    duration = 0.1  # 100ms
    samples = int(sample_rate * duration)
    audio = np.zeros(samples, dtype=np.float32)

    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="FLOAT")
    wav_bytes = buf.getvalue()

    buf2 = io.BytesIO(wav_bytes)
    data, sr = sf.read(buf2, dtype="float32")
    assert sr == sample_rate
    assert len(data) == samples


def test_feedback_thumbs_up():
    """Thumbs up fires callback with (True, None)."""
    from localwhisper.feedback import FeedbackController

    result = []
    ctrl = FeedbackController(lambda r, c: result.append((r, c)))
    ctrl.on_thumbs_up()
    assert result == [(True, None)]


def test_feedback_thumbs_down_with_comment():
    """Thumbs down fires callback with (False, comment)."""
    from localwhisper.feedback import FeedbackController

    result = []
    ctrl = FeedbackController(lambda r, c: result.append((r, c)))
    ctrl.on_thumbs_down("bad quality")
    assert result == [(False, "bad quality")]


def test_feedback_timeout():
    """Timeout fires callback with (None, None)."""
    from localwhisper.feedback import FeedbackController

    result = []
    ctrl = FeedbackController(lambda r, c: result.append((r, c)))
    ctrl.on_timeout()
    assert result == [(None, None)]


def test_feedback_callback_called_once():
    """Callback is only called once even with multiple actions."""
    from localwhisper.feedback import FeedbackController

    result = []
    ctrl = FeedbackController(lambda r, c: result.append((r, c)))
    ctrl.on_thumbs_up()
    ctrl.on_timeout()
    ctrl.on_thumbs_down("late")
    assert result == [(True, None)]


def test_feedback_cancel_timer():
    """cancel_timer() sets timer_cancelled flag."""
    from localwhisper.feedback import FeedbackController

    ctrl = FeedbackController(lambda r, c: None)
    assert not ctrl.timer_cancelled
    ctrl.cancel_timer()
    assert ctrl.timer_cancelled
