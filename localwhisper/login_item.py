import importlib
import logging
import subprocess
from pathlib import Path

from .paths import APP_NAME, bundle_path

log = logging.getLogger(__name__)


def _load_service_management():
    try:
        return importlib.import_module("ServiceManagement")
    except Exception:
        return None


def _main_app_service(service_management):
    service_cls = getattr(service_management, "SMAppService", None)
    if service_cls is None:
        return None
    for name in ("mainAppService", "mainApp"):
        factory = getattr(service_cls, name, None)
        if callable(factory):
            try:
                return factory()
            except Exception:
                log.warning("failed to create SMAppService via %s", name, exc_info=True)
    return None


def _call_service_method(service, method_name: str) -> bool:
    method = getattr(service, method_name, None)
    if method is None:
        return False
    try:
        result = method(None)
    except TypeError:
        result = method()
    if isinstance(result, tuple):
        return bool(result[0])
    return bool(result)


def _sync_with_service_management(enabled: bool) -> bool | None:
    service_management = _load_service_management()
    if service_management is None:
        return None
    service = _main_app_service(service_management)
    if service is None:
        return None
    try:
        method_name = (
            "registerAndReturnError_"
            if enabled
            else "unregisterAndReturnError_"
        )
        return _call_service_method(service, method_name)
    except Exception:
        log.warning("failed to sync login item via ServiceManagement", exc_info=True)
        return None


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _osascript_source(app_path: Path, enabled: bool) -> str:
    app_name = _escape_applescript(APP_NAME)
    if not enabled:
        return (
            'tell application "System Events"\n'
            f'if exists login item "{app_name}" then delete login item "{app_name}"\n'
            "end tell"
        )
    path = _escape_applescript(str(app_path))
    return (
        'tell application "System Events"\n'
        f'if exists login item "{app_name}" then delete login item "{app_name}"\n'
        "make login item at end with properties "
        f'{{name:"{app_name}", path:"{path}", hidden:false}}\n'
        "end tell"
    )


def _sync_with_osascript(app_path: Path, enabled: bool) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", _osascript_source(app_path, enabled)],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except Exception:
        log.warning("failed to sync login item via osascript", exc_info=True)
        return False


def sync(enabled: bool) -> bool:
    app_path = bundle_path()
    if app_path is None:
        log.info("launch at login is unavailable outside app bundle")
        return False
    result = _sync_with_service_management(enabled)
    if result is not None:
        return result
    return _sync_with_osascript(app_path, enabled)
