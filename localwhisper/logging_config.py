import contextlib
import logging
import sys

from .paths import DATA_DIR, LOG_PATH


def configure_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    with contextlib.suppress(OSError):
        handlers.append(logging.FileHandler(LOG_PATH, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        handlers=handlers,
        force=True,
    )
