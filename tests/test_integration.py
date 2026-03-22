"""Layer 2: Integration tests - real external services."""

from pathlib import Path

import pytest
import requests

FIXTURES_DIR = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.integration


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
class TestOllama:
    def test_ollama_responds(self):
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        assert r.status_code == 200

    def test_postprocessor_returns_text(self, default_config):
        from localwhisper.postprocessor import PostProcessor

        pp = PostProcessor(default_config)
        result = pp.process("тестовое сообщение")
        assert isinstance(result, str)
        assert len(result) > 0


class TestClipboard:
    def test_clipboard_roundtrip(self):
        import AppKit

        pb = AppKit.NSPasteboard.generalPasteboard()

        # Save current clipboard
        old = pb.stringForType_(AppKit.NSPasteboardTypeString)

        test_text = "localwhisper_test_clipboard_12345"
        pb.clearContents()
        pb.setString_forType_(test_text, AppKit.NSPasteboardTypeString)

        result = pb.stringForType_(AppKit.NSPasteboardTypeString)
        assert result == test_text

        # Restore
        if old:
            pb.clearContents()
            pb.setString_forType_(old, AppKit.NSPasteboardTypeString)


class TestSounds:
    def test_play_sound_no_error(self):
        from localwhisper.sounds import play_sound

        # Should not raise; plays a short system sound
        play_sound("/System/Library/Sounds/Tink.aiff")


@pytest.mark.slow
class TestTranscriber:
    def test_transcribe_silence(self, default_config):
        wav_path = FIXTURES_DIR / "silence_1s.wav"
        if not wav_path.exists():
            pytest.skip("Run scripts/generate_test_fixtures.py first")

        from localwhisper.transcriber import Transcriber

        t = Transcriber(default_config)
        result = t.transcribe(wav_path.read_bytes())
        assert isinstance(result, str)
