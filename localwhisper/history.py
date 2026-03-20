import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_DIR = Path.home() / ".local" / "share" / "localwhisper"
HISTORY_PATH = HISTORY_DIR / "history.jsonl"


def save_to_history(
    raw_text: str,
    processed_text: str,
    rating: bool | None = None,
    comment: str | None = None,
    history_path: Path | None = None,
):
    history_path = history_path or HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw": raw_text,
        "processed": processed_text,
        "rating": rating,
        "comment": comment,
    }

    with open(history_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
