import re
from pathlib import Path

import yaml

DICTIONARY_PATH = Path.home() / ".config" / "localwhisper" / "dictionary.yaml"


class UserDictionary:
    def __init__(self, path: Path | None = None):
        self._path = path or DICTIONARY_PATH
        self._entries: list[tuple[str, str]] = []
        self._load()

    @property
    def entries(self) -> list[tuple[str, str]]:
        return list(self._entries)

    def _load(self):
        if not self._path.exists():
            self._entries = []
            return
        with open(self._path) as f:
            data = yaml.safe_load(f) or []
        self._entries = [(item["from"], item["to"]) for item in data]

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"from": f, "to": t} for f, t in self._entries]
        with open(self._path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def add(self, from_word: str, to_word: str) -> str | None:
        for i, (f, t) in enumerate(self._entries):
            if f.lower() == from_word.lower():
                if t == to_word:
                    return None
                old_to = t
                self._entries[i] = (from_word, to_word)
                self._save()
                return old_to
        self._entries.append((from_word, to_word))
        self._save()
        return None

    def apply(self, text: str) -> str:
        sorted_entries = sorted(self._entries, key=lambda e: len(e[0]), reverse=True)
        for from_word, to_word in sorted_entries:
            pattern = r"\b" + re.escape(from_word) + r"\b"
            text = re.sub(pattern, to_word, text, flags=re.IGNORECASE)
        return text
