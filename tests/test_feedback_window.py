from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    try:
        from localwhisper import feedback_window

        feedback_window.FeedbackWindow._instance = None
    except Exception:
        pass


@pytest.fixture
def patched():
    with (
        patch("localwhisper.feedback_window.AppKit") as mock_appkit,
        patch("localwhisper.feedback_window.objc"),
    ):
        mock_window = MagicMock()
        mock_content = MagicMock()
        mock_window.contentView.return_value = mock_content
        win_alloc = mock_appkit.NSWindow.alloc.return_value
        win_alloc.initWithContentRect_styleMask_backing_defer_.return_value = (
            mock_window
        )
        mock_appkit.NSMakeRect = lambda x, y, w, h: (x, y, w, h)

        mock_scroll = MagicMock()
        mock_textview = MagicMock()
        mock_scroll.documentView.return_value = mock_textview
        mock_appkit.NSTextView.scrollableTextView.return_value = mock_scroll

        mock_button = MagicMock()
        mock_appkit.NSButton.alloc.return_value.initWithFrame_.return_value = (
            mock_button
        )

        mock_label = MagicMock()
        mock_appkit.NSTextField.labelWithString_.return_value = mock_label

        from localwhisper.feedback_window import FeedbackWindow

        fw = FeedbackWindow()
        yield fw


def test_feedback_window_singleton(patched):
    from localwhisper.feedback_window import FeedbackWindow

    FeedbackWindow._instance = None
    a = FeedbackWindow.shared()
    b = FeedbackWindow.shared()
    assert a is b


def test_show_populates_both_panes(patched):
    fw = patched
    on_confirm = MagicMock()
    on_cancel = MagicMock()

    fw.show("original text here", on_confirm, on_cancel)

    fw._original_view.setString_.assert_called_with("original text here")
    fw._corrected_view.setString_.assert_called_with("original text here")


def test_confirm_calls_callback_with_texts(patched):
    fw = patched
    on_confirm = MagicMock()

    fw._original_text = "original text"
    fw._on_confirm = on_confirm
    fw._corrected_view = MagicMock()
    fw._corrected_view.string.return_value = "edited text"

    fw._do_confirm()

    on_confirm.assert_called_once_with("original text", "edited text")


def test_cancel_calls_callback(patched):
    fw = patched
    on_cancel = MagicMock()

    fw._on_cancel = on_cancel
    fw._do_cancel()

    on_cancel.assert_called_once()
