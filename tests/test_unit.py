"""Layer 1: Unit tests - pure logic without external services."""

import io
import json

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


def test_postprocessor_empty_text(default_config):
    """Empty text returns empty without HTTP call."""
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.process("") == ""


def test_postprocessor_empty_text_openai(default_config):
    """Empty text returns empty without HTTP call (openai backend)."""
    from localwhisper.postprocessor import PostProcessor

    default_config["postprocessor"] = "openai"
    pp = PostProcessor(default_config)
    assert pp.process("") == ""


def test_postprocessor_backend_selection(default_config):
    """Backend is selected based on config."""
    from localwhisper.postprocessor import PostProcessor

    pp_ollama = PostProcessor(default_config)
    assert pp_ollama.backend == "ollama"

    default_config["postprocessor"] = "openai"
    pp_openai = PostProcessor(default_config)
    assert pp_openai.backend == "openai"


def test_pkce_generation():
    """PKCE verifier and challenge are valid."""
    import base64
    import hashlib

    from localwhisper.oauth import _generate_pkce

    verifier, challenge = _generate_pkce()
    assert len(verifier) > 40
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected


def test_build_auth_url():
    """Auth URL contains required OAuth params."""
    from localwhisper.oauth import _build_auth_url

    url = _build_auth_url("test_challenge", "test_state_12345678")
    assert "auth.openai.com" in url
    assert "client_id=" in url
    assert "code_challenge=test_challenge" in url
    assert "localhost%3A1455" in url or "localhost:1455" in url
    assert "%2Fauth%2Fcallback" in url or "/auth/callback" in url
    assert "S256" in url
    assert "state=test_state_12345678" in url


def test_token_save_load_roundtrip(tmp_path, monkeypatch):
    """Token save/load round-trip preserves data."""
    import localwhisper.oauth as oauth_mod

    token_path = tmp_path / "auth.json"
    monkeypatch.setattr(oauth_mod, "TOKEN_PATH", token_path)

    token_data = {
        "access_token": "test_access",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }
    oauth_mod._save_token(token_data)
    loaded = oauth_mod.load_token()
    assert loaded["access_token"] == "test_access"
    assert loaded["refresh_token"] == "test_refresh"
    assert "expires_at" in loaded


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

    rec = AudioRecorder(
        sample_rate=16000,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
    rec._frames = [np.zeros((8000, 1), dtype=np.float32)]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    assert rec.stop() == b""


def test_recorder_accepts_speech():
    """Audio with sufficient energy returns non-empty WAV bytes."""
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(
        sample_rate=16000,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
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

    rec = AudioRecorder(
        sample_rate=16000,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
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


def test_postprocessor_switch(default_config):
    """switch() changes backend and model at runtime."""
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.backend == "ollama"
    assert pp.ollama_model == default_config["ollama_model"]

    pp.switch("openai", "gpt-4o")
    assert pp.backend == "openai"
    assert pp.openai_model == "gpt-4o"

    pp.switch("ollama", "llama3:8b")
    assert pp.backend == "ollama"
    assert pp.ollama_model == "llama3:8b"


def test_recommended_ollama_models_survive_refresh():
    """refresh_ollama_models must keep recommended models even if not installed."""
    from localwhisper.constants import OLLAMA_MODELS
    from localwhisper.settings.tabs.models import merge_ollama_models

    recommended_ids = [model_id for model_id, _ in OLLAMA_MODELS]
    fetched = ["llama3:8b", "mistral:7b"]

    merged = merge_ollama_models(fetched)
    for rid in recommended_ids:
        assert rid in merged, f"{rid} must be in merged list"
    for f in fetched:
        assert f in merged


def test_ollama_request_has_no_thinking_params(default_config, monkeypatch):
    """gemma3 does not need think/no_think - request must be clean."""
    from unittest.mock import Mock

    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)

    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["json"] = json
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"message": {"content": "test"}}
        return resp

    monkeypatch.setattr("localwhisper.postprocessor.requests.post", mock_post)
    pp.process("hello")

    assert "think" not in captured["json"]
    system_msg = captured["json"]["messages"][0]["content"]
    assert "/no_think" not in system_msg


def test_ollama_timeout_is_30s(default_config, monkeypatch):
    """ollama timeout is 30s (no thinking overhead)."""
    from unittest.mock import Mock

    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)

    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"message": {"content": "test"}}
        return resp

    monkeypatch.setattr("localwhisper.postprocessor.requests.post", mock_post)
    pp.process("hello")

    assert captured["timeout"] == 30


def test_fetch_ollama_models_success(monkeypatch):
    """fetch_ollama_models parses /api/tags response."""
    from unittest.mock import Mock

    from localwhisper.models import fetch_ollama_models

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "models": [{"name": "gemma3:4b"}, {"name": "llama3:8b"}]
    }

    import localwhisper.models as models_mod

    monkeypatch.setattr(models_mod.requests, "get", lambda *a, **kw: mock_resp)

    result = fetch_ollama_models("http://localhost:11434")
    assert result == ["gemma3:4b", "llama3:8b"]


def test_fetch_ollama_models_failure(monkeypatch):
    """fetch_ollama_models returns empty list on error."""
    import localwhisper.models as models_mod
    from localwhisper.models import fetch_ollama_models

    monkeypatch.setattr(
        models_mod.requests,
        "get",
        lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("no ollama")),
    )

    assert fetch_ollama_models("http://localhost:11434") == []


def test_load_codex_models_success(tmp_path):
    """load_codex_models reads visible models from cache."""
    import json

    from localwhisper.models import load_codex_models

    cache = tmp_path / "models_cache.json"
    cache.write_text(
        json.dumps(
            {
                "models": [
                    {"slug": "gpt-5.4", "visibility": "list"},
                    {"slug": "gpt-5.3-codex", "visibility": "list"},
                    {"slug": "gpt-5.1", "visibility": "hide"},
                ]
            }
        )
    )

    result = load_codex_models(cache_path=cache)
    assert result == ["gpt-5.4", "gpt-5.3-codex"]


def test_load_codex_models_missing_file(tmp_path):
    """load_codex_models returns empty list when file missing."""
    from localwhisper.models import load_codex_models

    result = load_codex_models(cache_path=tmp_path / "nonexistent.json")
    assert result == []


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


def test_load_config_has_translate_to_default(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}\n")

    from localwhisper.config import load_config

    config = load_config(config_path=config_file)
    assert "translate_to" in config
    assert config["translate_to"] is None


def test_postprocessor_builds_translate_prompt(default_config):
    from localwhisper.postprocessor import PostProcessor

    default_config["translate_to"] = "English"
    pp = PostProcessor(default_config)
    assert pp.translate_to == "English"
    prompt = pp._build_prompt()
    assert "English" in prompt
    assert "Russian" not in prompt
    assert default_config["postprocess_prompt"] not in prompt


def test_postprocessor_no_translate_keeps_do_not_translate(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    prompt = pp._build_prompt()
    assert "Do NOT translate" in prompt


def test_postprocessor_no_translate_prompt(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    assert pp.translate_to is None
    prompt = pp._build_prompt()
    assert prompt == default_config["postprocess_prompt"]


def test_postprocessor_set_translate_to(default_config):
    from localwhisper.postprocessor import PostProcessor

    pp = PostProcessor(default_config)
    pp.set_translate_to("Japanese")
    assert pp.translate_to == "Japanese"
    assert "Japanese" in pp._build_prompt()

    pp.set_translate_to(None)
    assert pp.translate_to is None
    prompt = pp._build_prompt()
    assert prompt == default_config["postprocess_prompt"]


def test_save_config_roundtrip(tmp_path):
    """save_config persists updates and load_config reads them back."""
    from localwhisper.config import load_config, save_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "ru"}))

    save_config({"language": "en", "translate_to": "German"}, config_path=config_file)

    config = load_config(config_path=config_file)
    assert config["language"] == "en"
    assert config["translate_to"] == "German"


def test_save_config_preserves_existing_keys(tmp_path):
    """save_config does not drop keys not in the update."""
    from localwhisper.config import save_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"language": "ru", "ollama_model": "gemma3:4b"}))

    save_config({"language": "en"}, config_path=config_file)

    with open(config_file) as f:
        saved = yaml.safe_load(f)
    assert saved["language"] == "en"
    assert saved["ollama_model"] == "gemma3:4b"


def test_transcriber_language_mutable(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.language == "ru"
    t.language = "en"
    assert t.language == "en"


def test_focus_capture_returns_frontmost_app(monkeypatch):
    from unittest.mock import Mock

    mock_app = Mock()
    mock_workspace = Mock()
    mock_workspace.frontmostApplication.return_value = mock_app

    import localwhisper.focus as focus_mod

    monkeypatch.setattr(
        focus_mod.AppKit,
        "NSWorkspace",
        Mock(sharedWorkspace=Mock(return_value=mock_workspace)),
    )

    result = focus_mod.capture()
    assert result is mock_app
    mock_workspace.frontmostApplication.assert_called_once()


def test_focus_restore_activates_app(monkeypatch):
    from unittest.mock import Mock

    mock_app = Mock()
    mock_app.isTerminated.return_value = False
    mock_app.activateWithOptions_.return_value = True

    import localwhisper.focus as focus_mod

    monkeypatch.setattr(focus_mod, "_ACTIVATE_DELAY", 0)

    focus_mod.restore(mock_app)
    mock_app.activateWithOptions_.assert_called_once()


def test_focus_restore_skips_terminated_app():
    from unittest.mock import Mock

    mock_app = Mock()
    mock_app.isTerminated.return_value = True

    from localwhisper.focus import restore

    restore(mock_app)
    mock_app.activateWithOptions_.assert_not_called()


def _make_audio_array(duration=1.0, sample_rate=16000):
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * 440 * t)


def _make_wav_bytes(duration=1.0, sample_rate=16000):
    sine = _make_audio_array(duration, sample_rate)
    buf = io.BytesIO()
    sf.write(buf, sine, sample_rate, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def _make_engine(config, recorder=None, transcriber=None, postprocessor=None):
    from localwhisper.engine import LocalWhisperEngine

    engine = LocalWhisperEngine(config)
    if recorder:
        engine._recorder = recorder
    if transcriber:
        engine._transcriber = transcriber
    if postprocessor:
        engine._postprocessor = postprocessor
    return engine


def test_engine_on_and_emit(default_config):
    from localwhisper.engine import LocalWhisperEngine
    from localwhisper.events import EngineReady

    engine = LocalWhisperEngine(default_config)
    received = []
    engine.on(EngineReady, lambda e: received.append(e))
    engine._emit(EngineReady())
    assert len(received) == 1
    assert isinstance(received[0], EngineReady)


def test_engine_off_removes_callback(default_config):
    from localwhisper.engine import LocalWhisperEngine
    from localwhisper.events import EngineReady

    engine = LocalWhisperEngine(default_config)
    received = []

    def cb(e):
        received.append(e)

    engine.on(EngineReady, cb)
    engine.off(EngineReady, cb)
    engine._emit(EngineReady())
    assert len(received) == 0


def test_engine_multiple_listeners(default_config):
    from localwhisper.engine import LocalWhisperEngine
    from localwhisper.events import EngineReady

    engine = LocalWhisperEngine(default_config)
    a, b = [], []
    engine.on(EngineReady, lambda e: a.append(e))
    engine.on(EngineReady, lambda e: b.append(e))
    engine._emit(EngineReady())
    assert len(a) == 1
    assert len(b) == 1


def test_engine_initial_state(default_config):
    from localwhisper.engine import LocalWhisperEngine

    engine = LocalWhisperEngine(default_config)
    assert engine.state == "idle"


def test_engine_toggle_starts_recording(default_config):
    from unittest.mock import Mock

    from localwhisper.events import RecordingStarted

    mock_recorder = Mock()
    engine = _make_engine(default_config, recorder=mock_recorder)

    received = []
    engine.on(RecordingStarted, lambda e: received.append(e))
    engine.toggle()

    assert engine.state == "recording"
    mock_recorder.start.assert_called_once()
    assert len(received) == 1


def test_engine_toggle_recording_to_processing(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone, RecordingDone

    default_config["streaming"] = False
    done = _threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.return_value = "hello"
    mock_postprocessor = Mock()
    mock_postprocessor.process.return_value = "Hello."

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    done_events = []
    engine.on(RecordingDone, lambda e: done_events.append(e))
    engine.on(PostProcessingDone, lambda e: done.set())

    engine.toggle()
    assert engine.state == "recording"

    engine.toggle()
    done.wait(timeout=2)

    mock_recorder.stop_array.assert_called_once()
    assert len(done_events) == 1
    assert done_events[0].duration > 0


def test_engine_toggle_while_processing_ignored(default_config):
    import threading as _threading
    from unittest.mock import Mock

    default_config["streaming"] = False
    started = _threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()
    mock_transcriber = Mock()

    def slow_transcribe(x):
        started.set()
        _threading.Event().wait(2)
        return "text"

    mock_transcriber.transcribe_array.side_effect = slow_transcribe
    mock_postprocessor = Mock()
    mock_postprocessor.process.return_value = "text"

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    engine.toggle()
    engine.toggle()
    started.wait(timeout=2)
    assert engine.state == "processing"
    engine.toggle()
    assert engine.state == "processing"


def test_engine_recording_failed_device_error(default_config):
    from unittest.mock import Mock

    from localwhisper.events import RecordingFailed

    mock_recorder = Mock()
    mock_recorder.start.side_effect = Exception("no mic")

    engine = _make_engine(default_config, recorder=mock_recorder)

    received = []
    engine.on(RecordingFailed, lambda e: received.append(e))
    engine.toggle()

    assert engine.state == "idle"
    assert len(received) == 1
    assert received[0].reason == "device_error"


def test_engine_recording_failed_empty_audio(default_config):
    from unittest.mock import Mock

    from localwhisper.events import RecordingFailed

    default_config["streaming"] = False
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = None

    engine = _make_engine(default_config, recorder=mock_recorder)

    received = []
    engine.on(RecordingFailed, lambda e: received.append(e))

    engine.toggle()
    engine.toggle()

    assert engine.state == "idle"
    assert len(received) == 1
    assert received[0].reason == "no_audio"


def test_engine_cancel_during_recording(default_config):
    from unittest.mock import Mock

    from localwhisper.events import Cancelled

    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = None
    engine = _make_engine(default_config, recorder=mock_recorder)

    received = []
    engine.on(Cancelled, lambda e: received.append(e))

    engine.toggle()
    assert engine.state == "recording"

    engine.cancel()
    assert engine.state == "idle"
    assert len(received) == 1
    assert received[0].stage == "recording"


def test_engine_cancel_during_processing(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import Cancelled

    default_config["streaming"] = False
    started = _threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()
    mock_transcriber = Mock()

    def slow_transcribe(x):
        started.set()
        _threading.Event().wait(2)
        return "text"

    mock_transcriber.transcribe_array.side_effect = slow_transcribe
    mock_postprocessor = Mock()

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    received = []
    engine.on(Cancelled, lambda e: received.append(e))

    engine.toggle()
    engine.toggle()
    started.wait(timeout=2)
    assert engine.state == "processing"

    engine.cancel()
    assert len(received) == 1
    assert received[0].stage == "processing"


def test_engine_cancel_while_idle_ignored(default_config):
    from localwhisper.events import Cancelled

    engine = _make_engine(default_config)

    received = []
    engine.on(Cancelled, lambda e: received.append(e))
    engine.cancel()

    assert engine.state == "idle"
    assert len(received) == 0


def test_engine_transcribe_direct(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone, TranscriptionDone

    done = _threading.Event()
    mock_transcriber = Mock()
    mock_transcriber.transcribe.return_value = "hello world"
    mock_postprocessor = Mock()
    mock_postprocessor.process.return_value = "Hello, world."

    engine = _make_engine(
        default_config,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    td_events = []
    ppd_events = []
    engine.on(TranscriptionDone, lambda e: td_events.append(e))
    engine.on(PostProcessingDone, lambda e: (ppd_events.append(e), done.set()))

    engine.transcribe(b"fake_wav_data")
    done.wait(timeout=2)

    assert len(td_events) == 1
    assert td_events[0].raw_text == "hello world"
    assert len(ppd_events) == 1
    assert ppd_events[0].raw_text == "hello world"
    assert ppd_events[0].processed_text == "Hello, world."
    assert engine.state == "idle"


def test_engine_transcribe_while_recording_ignored(default_config):
    from unittest.mock import Mock

    mock_recorder = Mock()
    mock_transcriber = Mock()
    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
    )

    engine.toggle()
    assert engine.state == "recording"

    engine.transcribe(b"audio")
    mock_transcriber.transcribe.assert_not_called()


def test_engine_full_pipeline_events(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import (
        PostProcessingDone,
        PostProcessingStarted,
        RecordingDone,
        RecordingStarted,
        TranscriptionDone,
        TranscriptionStarted,
    )

    default_config["streaming"] = False
    done = _threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.return_value = "test"
    mock_postprocessor = Mock()
    mock_postprocessor.process.return_value = "Test."

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    events = []
    engine.on(RecordingStarted, lambda e: events.append(("recording_started", e)))
    engine.on(RecordingDone, lambda e: events.append(("recording_done", e)))
    engine.on(
        TranscriptionStarted, lambda e: events.append(("transcription_started", e))
    )
    engine.on(TranscriptionDone, lambda e: events.append(("transcription_done", e)))
    engine.on(PostProcessingStarted, lambda e: events.append(("pp_started", e)))
    engine.on(PostProcessingDone, lambda e: (events.append(("pp_done", e)), done.set()))

    engine.toggle()
    engine.toggle()
    done.wait(timeout=2)

    event_names = [name for name, _ in events]
    assert event_names == [
        "recording_started",
        "recording_done",
        "transcription_started",
        "transcription_done",
        "pp_started",
        "pp_done",
    ]


def test_engine_transcription_failed_event(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import TranscriptionFailed

    done = _threading.Event()
    mock_transcriber = Mock()
    mock_transcriber.transcribe.side_effect = RuntimeError("model crash")
    mock_postprocessor = Mock()

    engine = _make_engine(
        default_config,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    received = []
    engine.on(TranscriptionFailed, lambda e: (received.append(e), done.set()))

    engine.transcribe(b"audio")
    done.wait(timeout=2)

    assert len(received) == 1
    assert "model crash" in received[0].error
    assert engine.state == "idle"
    mock_postprocessor.process.assert_not_called()


def test_engine_empty_transcription_skips_postprocessing(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingStarted, TranscriptionDone

    done = _threading.Event()
    mock_transcriber = Mock()
    mock_transcriber.transcribe.return_value = ""
    mock_postprocessor = Mock()

    engine = _make_engine(
        default_config,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    td_events = []
    pp_events = []
    engine.on(TranscriptionDone, lambda e: (td_events.append(e), done.set()))
    engine.on(PostProcessingStarted, lambda e: pp_events.append(e))

    engine.transcribe(b"audio")
    done.wait(timeout=2)

    assert len(td_events) == 1
    assert td_events[0].raw_text == ""
    assert len(pp_events) == 0
    mock_postprocessor.process.assert_not_called()


def test_engine_update_config_language(default_config):
    from unittest.mock import Mock

    mock_transcriber = Mock()
    mock_transcriber.language = "ru"
    engine = _make_engine(default_config, transcriber=mock_transcriber)

    engine.update_config({"language": "en"})
    assert mock_transcriber.language == "en"


def test_engine_update_config_model(default_config):
    from unittest.mock import Mock

    mock_postprocessor = Mock()
    engine = _make_engine(default_config, postprocessor=mock_postprocessor)

    engine.update_config({"postprocessor": "openai", "openai_model": "gpt-5.4"})
    mock_postprocessor.switch.assert_called_once_with("openai", "gpt-5.4")


def test_engine_shutdown(default_config):
    from unittest.mock import Mock

    mock_transcriber = Mock()
    engine = _make_engine(default_config, transcriber=mock_transcriber)
    engine.shutdown()
    mock_transcriber._unload.assert_called_once()


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


def test_engine_update_config_input_device(default_config):
    from unittest.mock import Mock

    mock_recorder = Mock()
    mock_recorder.input_device = None
    engine = _make_engine(default_config, recorder=mock_recorder)

    engine.update_config({"input_device": "usb mic"})
    assert mock_recorder.input_device == "usb mic"

    engine.update_config({"input_device": None})
    assert mock_recorder.input_device is None


def test_config_has_postprocess_default(default_config):
    assert "postprocess" in default_config
    assert default_config["postprocess"] is True


def test_config_has_streaming_defaults(default_config):
    assert "streaming" in default_config
    assert default_config["streaming"] is True
    assert "chunk_duration" in default_config
    assert default_config["chunk_duration"] == 5.0


def test_engine_skips_postprocessing_when_disabled(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    done = _threading.Event()
    default_config["postprocess"] = False

    mock_transcriber = Mock()
    mock_transcriber.transcribe.return_value = "hello"
    mock_postprocessor = Mock()

    engine = _make_engine(
        default_config,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    ppd_events = []
    engine.on(PostProcessingDone, lambda e: (ppd_events.append(e), done.set()))

    engine.transcribe(b"audio")
    done.wait(timeout=2)

    assert len(ppd_events) == 1
    assert ppd_events[0].raw_text == "hello"
    assert ppd_events[0].processed_text == "hello"
    mock_postprocessor.process.assert_not_called()


def test_engine_runs_postprocessing_when_enabled(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    done = _threading.Event()
    default_config["postprocess"] = True

    mock_transcriber = Mock()
    mock_transcriber.transcribe.return_value = "hello"
    mock_postprocessor = Mock()
    mock_postprocessor.process.return_value = "Hello."

    engine = _make_engine(
        default_config,
        transcriber=mock_transcriber,
        postprocessor=mock_postprocessor,
    )

    ppd_events = []
    engine.on(PostProcessingDone, lambda e: (ppd_events.append(e), done.set()))

    engine.transcribe(b"audio")
    done.wait(timeout=2)

    assert len(ppd_events) == 1
    assert ppd_events[0].processed_text == "Hello."
    mock_postprocessor.process.assert_called_once_with("hello")


def test_transcriber_transcribe_array(default_config):
    from unittest.mock import Mock

    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    t._model_loaded = True
    t._mlx_whisper = Mock()
    t._mlx_whisper.transcribe.return_value = {"text": "hello world"}

    audio = np.random.randn(16000).astype(np.float32)
    result = t.transcribe_array(audio)

    assert result == "hello world"
    call_args = t._mlx_whisper.transcribe.call_args
    assert isinstance(call_args[0][0], np.ndarray)


def test_transcriber_transcribe_bytes_delegates_to_array(default_config):
    from unittest.mock import Mock

    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    t._model_loaded = True
    t._mlx_whisper = Mock()
    t._mlx_whisper.transcribe.return_value = {"text": "test"}

    wav_bytes = _make_wav_bytes(duration=0.5)
    result = t.transcribe(wav_bytes)

    assert result == "test"
    call_args = t._mlx_whisper.transcribe.call_args
    assert isinstance(call_args[0][0], np.ndarray)


def test_transcriber_transcribe_array_empty(default_config):
    from localwhisper.transcriber import Transcriber

    t = Transcriber(default_config)
    assert t.transcribe_array(np.array([], dtype=np.float32)) == ""
    assert not t._model_loaded


def test_recorder_stop_array_returns_numpy():
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(
        sample_rate=16000,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)
    rec._frames = [sine]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    result = rec.stop_array()
    assert isinstance(result, np.ndarray)
    assert len(result) == 16000


def test_recorder_stop_array_returns_none_on_silence():
    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(
        sample_rate=16000,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
    rec._frames = [np.zeros((8000, 1), dtype=np.float32)]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = None

    assert rec.stop_array() is None


def test_focus_restore_reduced_delay():
    from localwhisper.focus import _ACTIVATE_DELAY

    assert _ACTIVATE_DELAY == 0.05


def test_recorder_start_skips_volume_when_none(monkeypatch):
    from unittest.mock import Mock, patch

    import sounddevice as sd

    from localwhisper.recorder import AudioRecorder

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = AudioRecorder(
        sample_rate=16000,
        recording_volume=None,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )

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
    from unittest.mock import patch

    from localwhisper.recorder import AudioRecorder

    rec = AudioRecorder(
        sample_rate=16000,
        recording_volume=100,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)
    rec._frames = [sine]
    rec._recording = False
    rec._stream = type("S", (), {"stop": lambda s: None, "close": lambda s: None})()
    rec._saved_volume = 75

    calls = []

    def fake_set_volume(vol):
        calls.append(("set", vol))

    with patch.object(rec, "_set_input_volume", side_effect=fake_set_volume):
        result = rec.stop_array()

    assert result is not None
    import time

    time.sleep(0.1)
    assert ("set", 75) in calls


def test_chunk_accumulator_yields_at_threshold():
    from localwhisper.streaming import ChunkAccumulator

    acc = ChunkAccumulator(chunk_duration=1.0, sample_rate=16000)
    chunk = acc.add_frames(np.zeros(16000, dtype=np.float32))
    assert chunk is not None
    assert len(chunk) == 16000


def test_chunk_accumulator_no_yield_below_threshold():
    from localwhisper.streaming import ChunkAccumulator

    acc = ChunkAccumulator(chunk_duration=1.0, sample_rate=16000)
    chunk = acc.add_frames(np.zeros(8000, dtype=np.float32))
    assert chunk is None


def test_chunk_accumulator_flush_returns_remainder():
    from localwhisper.streaming import ChunkAccumulator

    acc = ChunkAccumulator(chunk_duration=1.0, sample_rate=16000)
    acc.add_frames(np.ones(5000, dtype=np.float32))
    remainder = acc.flush()
    assert remainder is not None
    assert len(remainder) == 5000


def test_chunk_accumulator_flush_empty_returns_none():
    from localwhisper.streaming import ChunkAccumulator

    acc = ChunkAccumulator(chunk_duration=1.0, sample_rate=16000)
    assert acc.flush() is None


def test_chunk_accumulator_multiple_adds():
    from localwhisper.streaming import ChunkAccumulator

    acc = ChunkAccumulator(chunk_duration=1.0, sample_rate=16000)
    assert acc.add_frames(np.zeros(8000, dtype=np.float32)) is None
    chunk = acc.add_frames(np.zeros(8000, dtype=np.float32))
    assert chunk is not None
    assert len(chunk) == 16000
    assert acc.flush() is None


def test_streaming_transcriber_processes_chunks():
    from unittest.mock import Mock

    from localwhisper.streaming import StreamingTranscriber

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.side_effect = ["one", "two", "three"]

    st = StreamingTranscriber(mock_transcriber)
    st.start()
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    result = st.finish()

    assert result == "one two three"
    assert mock_transcriber.transcribe_array.call_count == 3


def test_streaming_transcriber_cancel():
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.streaming import StreamingTranscriber

    started = _threading.Event()
    mock_transcriber = Mock()

    def slow_transcribe(audio):
        started.set()
        _threading.Event().wait(2)
        return "text"

    mock_transcriber.transcribe_array.side_effect = slow_transcribe

    st = StreamingTranscriber(mock_transcriber)
    st.start()
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    started.wait(timeout=2)
    result = st.cancel()
    assert isinstance(result, str)


def test_streaming_transcriber_empty_chunks_filtered():
    from unittest.mock import Mock

    from localwhisper.streaming import StreamingTranscriber

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.side_effect = ["hello", "", "world"]

    st = StreamingTranscriber(mock_transcriber)
    st.start()
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    st.submit_chunk(np.zeros(16000, dtype=np.float32))
    result = st.finish()

    assert result == "hello world"


def test_engine_streaming_transcribes_during_recording(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    default_config["streaming"] = True
    default_config["chunk_duration"] = 0.5
    default_config["postprocess"] = False

    done = _threading.Event()
    mock_recorder = Mock()

    def fake_start(chunk_callback=None):
        if chunk_callback:
            chunk_callback(np.zeros(8000, dtype=np.float32))
            chunk_callback(np.zeros(8000, dtype=np.float32))

    mock_recorder.start.side_effect = fake_start
    mock_recorder.stop_array.return_value = None

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.return_value = "chunk"

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
    )

    ppd_events = []
    engine.on(PostProcessingDone, lambda e: (ppd_events.append(e), done.set()))

    engine.toggle()
    engine.toggle()
    done.wait(timeout=2)

    assert mock_transcriber.transcribe_array.call_count == 2


def test_engine_non_streaming_uses_batch(default_config):
    import threading as _threading
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    default_config["streaming"] = False
    default_config["postprocess"] = False

    done = _threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()

    mock_transcriber = Mock()
    mock_transcriber.transcribe_array.return_value = "batch result"

    engine = _make_engine(
        default_config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
    )

    ppd_events = []
    engine.on(PostProcessingDone, lambda e: (ppd_events.append(e), done.set()))

    engine.toggle()
    engine.toggle()
    done.wait(timeout=2)

    assert len(ppd_events) == 1
    assert ppd_events[0].processed_text == "batch result"
    mock_transcriber.transcribe_array.assert_called_once()


def test_recorder_start_no_device_refresh(monkeypatch):
    from unittest.mock import Mock, patch

    import sounddevice as sd

    from localwhisper.recorder import AudioRecorder

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = AudioRecorder(
        sample_rate=16000,
        recording_volume=None,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )

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
    from unittest.mock import Mock, patch

    import sounddevice as sd

    from localwhisper.recorder import AudioRecorder

    monkeypatch.setattr(sd, "_terminate", Mock())
    monkeypatch.setattr(sd, "_initialize", Mock())

    rec = AudioRecorder(
        sample_rate=16000,
        recording_volume=100,
        min_audio_energy=0.003,
        min_recording_duration=0.3,
    )

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

    import time

    time.sleep(0.2)
    assert rec._saved_volume == 50
    assert 100 in volume_calls
