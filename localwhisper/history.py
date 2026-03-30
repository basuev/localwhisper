import json
from datetime import UTC, datetime
from pathlib import Path

from .paths import DATA_DIR

HISTORY_DIR = DATA_DIR
HISTORY_PATH = HISTORY_DIR / "history.jsonl"


def save_to_history(
    raw_text: str,
    processed_text: str,
    history_path: Path | None = None,
):
    history_path = history_path or HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "raw": raw_text,
        "processed": processed_text,
    }

    with open(history_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
