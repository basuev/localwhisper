import threading

import numpy as np


def _make_audio_array(duration=1.0, sample_rate=16000):
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * 440 * t)


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
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone, RecordingDone

    default_config["streaming"] = False
    done = threading.Event()
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
    from unittest.mock import Mock

    default_config["streaming"] = False
    started = threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()
    mock_transcriber = Mock()

    def slow_transcribe(x):
        started.set()
        threading.Event().wait(2)
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
    from unittest.mock import Mock

    from localwhisper.events import Cancelled

    default_config["streaming"] = False
    started = threading.Event()
    mock_recorder = Mock()
    mock_recorder.stop_array.return_value = _make_audio_array()
    mock_transcriber = Mock()

    def slow_transcribe(x):
        started.set()
        threading.Event().wait(2)
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
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone, TranscriptionDone

    done = threading.Event()
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
    done = threading.Event()
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
    from unittest.mock import Mock

    from localwhisper.events import TranscriptionFailed

    done = threading.Event()
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
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingStarted, TranscriptionDone

    done = threading.Event()
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


def test_engine_update_config_input_device(default_config):
    from unittest.mock import Mock

    mock_recorder = Mock()
    mock_recorder.input_device = None
    engine = _make_engine(default_config, recorder=mock_recorder)

    engine.update_config({"input_device": "usb mic"})
    assert mock_recorder.input_device == "usb mic"

    engine.update_config({"input_device": None})
    assert mock_recorder.input_device is None


def test_engine_shutdown(default_config):
    from unittest.mock import Mock

    mock_transcriber = Mock()
    engine = _make_engine(default_config, transcriber=mock_transcriber)
    engine.shutdown()
    mock_transcriber._unload.assert_called_once()


def test_engine_skips_postprocessing_when_disabled(default_config):
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    done = threading.Event()
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
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    done = threading.Event()
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
    args, kwargs = mock_postprocessor.process.call_args
    assert args == ("hello",)
    assert "cancel_check" in kwargs


def test_engine_streaming_transcribes_during_recording(default_config):
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    default_config["streaming"] = True
    default_config["chunk_duration"] = 0.5
    default_config["postprocess"] = False

    done = threading.Event()
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
    from unittest.mock import Mock

    from localwhisper.events import PostProcessingDone

    default_config["streaming"] = False
    default_config["postprocess"] = False

    done = threading.Event()
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
