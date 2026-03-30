import difflib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

CORRECTIONS_PATH = Path.home() / ".config" / "localwhisper" / "corrections.yaml"


@dataclass
class CorrectionEntry:
    timestamp: str
    original: str
    corrected: str


class CorrectionsStore:
    def __init__(self, path: Path | None = None, max_entries: int = 50):
        self._path = path or CORRECTIONS_PATH
        self._max_entries = max_entries
        self._entries: list[CorrectionEntry] = []
        self._load()

    @property
    def entries(self) -> list[CorrectionEntry]:
        return list(self._entries)

    def _load(self):
        if not self._path.exists():
            self._entries = []
            return
        with open(self._path) as f:
            data = yaml.safe_load(f) or []
        self._entries = [CorrectionEntry(**item) for item in data]

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            yaml.safe_dump(
                [asdict(entry) for entry in self._entries],
                f,
                default_flow_style=False,
                allow_unicode=True,
            )

    def add(self, original: str, corrected: str) -> None:
        updated = CorrectionEntry(
            timestamp=datetime.now(UTC).isoformat(),
            original=original,
            corrected=corrected,
        )
        for i, entry in enumerate(self._entries):
            if entry.original == original and entry.corrected == corrected:
                self._entries.pop(i)
                break
        self._entries.append(updated)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        self._save()

    def get_recent(self, n: int = 10) -> list[CorrectionEntry]:
        return list(self._entries[-n:])

    def get_relevant(self, text: str, n: int = 5) -> list[CorrectionEntry]:
        return sorted(
            self._entries,
            key=lambda entry: difflib.SequenceMatcher(
                None, text, entry.original
            ).ratio(),
            reverse=True,
        )[:n]
