import threading

import numpy as np


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
    from unittest.mock import Mock

    from localwhisper.streaming import StreamingTranscriber

    started = threading.Event()
    mock_transcriber = Mock()

    def slow_transcribe(audio):
        started.set()
        threading.Event().wait(2)
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
