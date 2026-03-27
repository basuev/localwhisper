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
