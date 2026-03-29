import difflib
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
        for _i, (f, t) in enumerate(self._entries):
            if f.lower() == from_word.lower():
                if t == to_word:
                    return None
                return t
        self._entries.append((from_word, to_word))
        self._save()
        return None

    def resolve_conflict(self, from_word: str, to_word: str):
        for i, (f, _t) in enumerate(self._entries):
            if f.lower() == from_word.lower():
                self._entries[i] = (from_word, to_word)
                self._save()
                return
        self._entries.append((from_word, to_word))
        self._save()

    @staticmethod
    def diff(original: str, corrected: str) -> list[tuple[str, str]]:
        original_words = original.split()
        corrected_words = corrected.split()
        matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
        replacements = []
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "replace" and (i2 - i1) == (j2 - j1):
                for orig, corr in zip(
                    original_words[i1:i2], corrected_words[j1:j2], strict=True
                ):
                    if orig != corr:
                        replacements.append((orig, corr))
        return replacements

    @staticmethod
    def is_similar(text_a: str, text_b: str, threshold: float) -> bool:
        return difflib.SequenceMatcher(None, text_a, text_b).ratio() >= threshold

    def apply(self, text: str) -> str:
        sorted_entries = sorted(self._entries, key=lambda e: len(e[0]), reverse=True)
        for from_word, to_word in sorted_entries:
            pattern = r"\b" + re.escape(from_word) + r"\b"
            text = re.sub(pattern, to_word, text, flags=re.IGNORECASE | re.UNICODE)
        return text
