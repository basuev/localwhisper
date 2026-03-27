from collections.abc import Callable
from typing import Any

import AppKit

from localwhisper.constants import SPEECH_LANGUAGES, TRANSLATE_LANGUAGES
from localwhisper.settings.controls import ROW_HEIGHT, LabeledDropdown, LabeledToggle
from localwhisper.settings.window import (
    CONTAINER_HEIGHT,
    TAB_PADDING_TOP,
    TAB_PADDING_X,
    TAB_ROW_GAP,
    WINDOW_WIDTH,
)

HOTKEY_CHOICES = [
    ("Right Option", 61),
    ("Left Option", 58),
    ("Fn", 63),
    ("Right Command", 54),
    ("Right Control", 62),
]

_code_to_name = {code: name for code, name in SPEECH_LANGUAGES}
_name_to_code = {name: code for code, name in SPEECH_LANGUAGES}
_hotkey_name_to_code = {name: code for name, code in HOTKEY_CHOICES}
_hotkey_code_to_name = {code: name for name, code in HOTKEY_CHOICES}


class GeneralTab:
    def __init__(self, config: dict, on_change: Callable[[str, Any], None]):
        self._on_change = on_change

        self._view = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, CONTAINER_HEIGHT)
        )

        y = CONTAINER_HEIGHT - TAB_PADDING_TOP - ROW_HEIGHT

        self._language = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Speech Language",
            [name for _, name in SPEECH_LANGUAGES],
            self._on_language_changed,
        )
        self._language.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._language)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._translate = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Translation",
            TRANSLATE_LANGUAGES,
            self._on_translate_changed,
        )
        self._translate.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._translate)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._hotkey = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Hotkey",
            [name for name, _ in HOTKEY_CHOICES],
            self._on_hotkey_changed,
        )
        self._hotkey.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._hotkey)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._blob_theme = LabeledToggle.alloc().initWithLabel_callback_(
            "Light Blob",
            self._on_blob_theme_changed,
        )
        self._blob_theme.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._blob_theme)

        self.sync(config)

    @property
    def view(self) -> AppKit.NSView:
        return self._view

    def sync(self, config: dict):
        lang_code = config.get("language", "ru")
        lang_name = _code_to_name.get(lang_code, "Russian")
        self._language.set_value(lang_name)

        translate_to = config.get("translate_to")
        self._translate.set_value(translate_to if translate_to else "Off")

        hotkey_code = config.get("hotkey_keycode", 61)
        hotkey_name = _hotkey_code_to_name.get(hotkey_code, "Right Option")
        self._hotkey.set_value(hotkey_name)

        blob_theme = config.get("blob_theme", "dark")
        self._blob_theme.set_value(blob_theme == "light")

    def _on_language_changed(self, name: str):
        code = _name_to_code.get(name, "ru")
        self._on_change("language", code)

    def _on_translate_changed(self, name: str):
        value = None if name == "Off" else name
        self._on_change("translate_to", value)

    def _on_hotkey_changed(self, name: str):
        code = _hotkey_name_to_code.get(name, 61)
        self._on_change("hotkey_keycode", code)

    def _on_blob_theme_changed(self, is_on: bool):
        self._on_change("blob_theme", "light" if is_on else "dark")
