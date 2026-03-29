import time


def test_single_click_triggers_callback():
    from unittest.mock import MagicMock

    from localwhisper.hotkey import DoubleClickDetector

    callback = MagicMock()
    feedback_callback = MagicMock()
    detector = DoubleClickDetector(callback, feedback_callback, timeout_ms=100)

    detector.on_release()
    time.sleep(0.15)
    detector.flush()

    callback.assert_called_once()
    feedback_callback.assert_not_called()


def test_double_click_triggers_feedback():
    from unittest.mock import MagicMock

    from localwhisper.hotkey import DoubleClickDetector

    callback = MagicMock()
    feedback_callback = MagicMock()
    detector = DoubleClickDetector(callback, feedback_callback, timeout_ms=100)

    detector.on_release()
    time.sleep(0.03)
    detector.on_release()

    feedback_callback.assert_called_once()
    callback.assert_not_called()


def test_slow_double_click_triggers_two_singles():
    from unittest.mock import MagicMock

    from localwhisper.hotkey import DoubleClickDetector

    callback = MagicMock()
    feedback_callback = MagicMock()
    detector = DoubleClickDetector(callback, feedback_callback, timeout_ms=100)

    detector.on_release()
    time.sleep(0.15)
    detector.flush()
    detector.on_release()
    time.sleep(0.15)
    detector.flush()

    assert callback.call_count == 2
    feedback_callback.assert_not_called()
