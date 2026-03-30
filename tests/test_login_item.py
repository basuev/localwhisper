def test_sync_skips_outside_app_bundle(monkeypatch):
    import localwhisper.login_item as login_item

    monkeypatch.setattr(login_item, "bundle_path", lambda: None)

    assert login_item.sync(True) is False


def test_sync_uses_service_management_when_available(monkeypatch):
    import pathlib

    import localwhisper.login_item as login_item

    monkeypatch.setattr(
        login_item,
        "bundle_path",
        lambda: pathlib.Path("/Applications/localwhisper.app"),
    )
    monkeypatch.setattr(
        login_item,
        "_sync_with_service_management",
        lambda enabled: enabled,
    )

    assert login_item.sync(True) is True


def test_sync_falls_back_to_osascript(monkeypatch):
    import pathlib

    import localwhisper.login_item as login_item

    monkeypatch.setattr(
        login_item,
        "bundle_path",
        lambda: pathlib.Path("/Applications/localwhisper.app"),
    )
    monkeypatch.setattr(
        login_item,
        "_sync_with_service_management",
        lambda enabled: None,
    )

    called = {}

    def fake_sync(app_path, enabled):
        called["app_path"] = app_path
        called["enabled"] = enabled
        return True

    monkeypatch.setattr(login_item, "_sync_with_osascript", fake_sync)

    assert login_item.sync(False) is True
    assert called["app_path"] == pathlib.Path("/Applications/localwhisper.app")
    assert called["enabled"] is False
