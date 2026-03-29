import math
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def overlay():
    with patch("localwhisper.overlay.AppKit"), patch("localwhisper.overlay.Quartz"):
        from localwhisper.overlay import AudioOverlay

        ov = AudioOverlay.__new__(AudioOverlay)
        ov._panel = None
        ov._blob_view = None
        ov._timer = None
        ov._amplitude = 0.0
        ov._lock = __import__("threading").Lock()
        ov._start_time = 0.0
        ov._theme = "dark"
        ov._mode = "recording"
        ov._pulse_start = None
        return ov


def test_set_mode_pulse_stores_mode(overlay):
    overlay._blob_view = MagicMock()
    overlay._timer = MagicMock()
    with patch("localwhisper.overlay.AppKit"):
        overlay.set_mode("pulse")
    assert overlay._mode == "pulse"


def test_pulse_tick_amplitude_follows_sine(overlay):
    from localwhisper.overlay import PULSE_DURATION

    overlay._mode = "pulse"
    overlay._pulse_start = 0.0
    overlay._blob_view = MagicMock()

    t = PULSE_DURATION / 2
    overlay._start_time = -t
    overlay._pulse_start = -t

    with patch("localwhisper.overlay.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        overlay._tick()

    call_args = overlay._blob_view.setAmplitude_.call_args[0][0]
    expected = math.sin(math.pi * 0.5)
    assert abs(call_args - expected) < 0.01


def test_pulse_auto_hides_after_duration(overlay):
    from localwhisper.overlay import PULSE_DURATION

    overlay._mode = "pulse"
    overlay._blob_view = MagicMock()
    overlay._panel = MagicMock()
    overlay._timer = MagicMock()

    overlay._pulse_start = 0.0
    overlay._start_time = 0.0

    with patch("localwhisper.overlay.time") as mock_time:
        mock_time.monotonic.return_value = PULSE_DURATION + 0.01
        overlay._tick()

    overlay._panel.orderOut_.assert_called_once()


def test_pulse_does_not_use_shimmer(overlay):
    overlay._blob_view = MagicMock()
    overlay._timer = MagicMock()
    with patch("localwhisper.overlay.AppKit"):
        overlay.set_mode("pulse")
    overlay._blob_view.setShimmer_.assert_called_with(False)
