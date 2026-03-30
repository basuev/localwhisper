import sys
from pathlib import Path

try:
    from Foundation import NSBundle
except ImportError:
    NSBundle = None

APP_NAME = "localwhisper"
APP_BUNDLE_ID = "com.localwhisper.app"
CONFIG_DIR = Path.home() / ".config" / "localwhisper"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DATA_DIR = Path.home() / ".local" / "share" / "localwhisper"
LOG_PATH = DATA_DIR / "app.log"


def bundle_path() -> Path | None:
    if NSBundle is None:
        return None
    bundle = NSBundle.mainBundle()
    if bundle is None:
        return None
    path = bundle.bundlePath()
    if not path:
        return None
    bundle_dir = Path(str(path))
    if bundle_dir.suffix != ".app":
        return None
    return bundle_dir


def is_bundled_app() -> bool:
    return bundle_path() is not None


def resources_path() -> Path | None:
    if NSBundle is None or not is_bundled_app():
        return None
    bundle = NSBundle.mainBundle()
    path = bundle.resourcePath()
    if not path:
        return None
    return Path(str(path))


def executable_path() -> Path:
    if NSBundle is not None:
        bundle = NSBundle.mainBundle()
        if bundle is not None:
            path = bundle.executablePath()
            if path:
                return Path(str(path))
    return Path(sys.executable)


def config_example_path() -> Path | None:
    repo_path = Path(__file__).resolve().parent.parent / "config.example.yaml"
    if repo_path.exists():
        return repo_path
    resources_dir = resources_path()
    if resources_dir is None:
        return None
    bundled_path = resources_dir / "config.example.yaml"
    if bundled_path.exists():
        return bundled_path
    return None
