import math
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def overlay():
    with patch("localwhisper.overlay.AppKit"), patch("localwhisper.overlay.Quartz"):
        from localwhisper.overlay import AudioOverlay

        ov = AudioOverlay.__new__(AudioOverlay)
        ov._panels = []
        ov._timer = None
        ov._amplitude = 0.0
        ov._lock = __import__("threading").Lock()
        ov._start_time = 0.0
        ov._theme = "dark"
        ov._mode = "recording"
        ov._pulse_start = None
        return ov


def test_set_mode_pulse_stores_mode(overlay):
    overlay._panels = [(MagicMock(), MagicMock())]
    overlay._timer = MagicMock()
    with patch("localwhisper.overlay.AppKit"):
        overlay.set_mode("pulse")
    assert overlay._mode == "pulse"


def test_pulse_tick_amplitude_follows_sine(overlay):
    from localwhisper.overlay import PULSE_DURATION

    overlay._mode = "pulse"
    overlay._pulse_start = 0.0
    mock_blob = MagicMock()
    overlay._panels = [(MagicMock(), mock_blob)]

    t = PULSE_DURATION / 2
    overlay._start_time = -t
    overlay._pulse_start = -t

    with patch("localwhisper.overlay.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        overlay._tick()

    call_args = mock_blob.setAmplitude_.call_args[0][0]
    expected = math.sin(math.pi * 0.5)
    assert abs(call_args - expected) < 0.01


def test_pulse_auto_hides_after_duration(overlay):
    from localwhisper.overlay import PULSE_DURATION

    overlay._mode = "pulse"
    mock_panel = MagicMock()
    overlay._panels = [(mock_panel, MagicMock())]
    overlay._timer = MagicMock()

    overlay._pulse_start = 0.0
    overlay._start_time = 0.0

    with patch("localwhisper.overlay.time") as mock_time:
        mock_time.monotonic.return_value = PULSE_DURATION + 0.01
        overlay._tick()

    mock_panel.orderOut_.assert_called_once()


def test_pulse_does_not_use_shimmer(overlay):
    mock_blob = MagicMock()
    overlay._panels = [(MagicMock(), mock_blob)]
    overlay._timer = MagicMock()
    with patch("localwhisper.overlay.AppKit"):
        overlay.set_mode("pulse")
    mock_blob.setShimmer_.assert_called_with(False)


def test_tick_updates_all_blob_views(overlay):
    blob1 = MagicMock()
    blob2 = MagicMock()
    overlay._panels = [(MagicMock(), blob1), (MagicMock(), blob2)]
    overlay._mode = "recording"
    overlay._amplitude = 0.5
    overlay._start_time = 0.0

    with patch("localwhisper.overlay.time") as mock_time:
        mock_time.monotonic.return_value = 1.0
        overlay._tick()

    for blob in (blob1, blob2):
        blob.setAmplitude_.assert_called_once()
        blob.setTime_.assert_called_once()
        blob.setNeedsDisplay_.assert_called_once_with(True)


def test_hide_hides_all_panels(overlay):
    panel1 = MagicMock()
    panel2 = MagicMock()
    overlay._panels = [(panel1, MagicMock()), (panel2, MagicMock())]
    overlay._timer = MagicMock()

    overlay.hide()

    panel1.orderOut_.assert_called_once()
    panel2.orderOut_.assert_called_once()


def test_set_theme_updates_all_blob_views(overlay):
    blob1 = MagicMock()
    blob2 = MagicMock()
    overlay._panels = [(MagicMock(), blob1), (MagicMock(), blob2)]

    overlay.set_theme("light")

    blob1.setTheme_.assert_called_once_with("light")
    blob2.setTheme_.assert_called_once_with("light")
