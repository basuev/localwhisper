from collections.abc import Callable
from typing import Any

import AppKit
import objc

from localwhisper.constants import OLLAMA_MODELS, WHISPER_MODELS
from localwhisper.settings.controls import (
    LABEL_WIDTH,
    LabeledDropdown,
    LabeledTextField,
    ROW_HEIGHT,
    TOTAL_WIDTH,
    _make_label,
)
from localwhisper.settings.window import (
    CONTAINER_HEIGHT,
    TAB_PADDING_TOP,
    TAB_PADDING_X,
    TAB_ROW_GAP,
    WINDOW_WIDTH,
)

WHISPER_DISPLAY_TO_ID = {label: model_id for model_id, label in WHISPER_MODELS}
WHISPER_ID_TO_DISPLAY = {model_id: label for model_id, label in WHISPER_MODELS}

RECOMMENDED_OLLAMA_IDS = [model_id for model_id, _ in OLLAMA_MODELS]

POSTPROCESSOR_BACKENDS = ["Ollama", "OpenAI"]
BACKEND_DISPLAY_TO_KEY = {"Ollama": "ollama", "OpenAI": "openai"}
BACKEND_KEY_TO_DISPLAY = {"ollama": "Ollama", "openai": "OpenAI"}


def merge_ollama_models(fetched: list[str]) -> list[str]:
    seen = set(fetched)
    tail = [r for r in RECOMMENDED_OLLAMA_IDS if r not in seen]
    return fetched + tail


class _LoginButtonDelegate(AppKit.NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(_LoginButtonDelegate, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def onLoginClicked_(self, sender):
        self._callback()


class ModelsTab:
    def __init__(
        self,
        config: dict,
        on_change: Callable[[str, Any], None],
        on_openai_login: Callable[[], None],
    ):
        self._on_change = on_change
        self._on_openai_login = on_openai_login
        self._current_backend = config.get("postprocessor", "ollama")
        recommended = [model_id for model_id, _ in OLLAMA_MODELS]
        current = config.get("ollama_model", "gemma3:4b")
        self._ollama_models: list[str] = (
            recommended if current in recommended else [current] + recommended
        )
        self._openai_models: list[str] = [config.get("openai_model", "gpt-5.4")]

        self._view = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, CONTAINER_HEIGHT)
        )

        y = CONTAINER_HEIGHT - TAB_PADDING_TOP - ROW_HEIGHT

        self._whisper_dropdown = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Whisper Model",
            [label for _, label in WHISPER_MODELS],
            self._on_whisper_changed,
        )
        self._whisper_dropdown.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._whisper_dropdown)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._backend_dropdown = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Postprocessor",
            POSTPROCESSOR_BACKENDS,
            self._on_backend_changed,
        )
        self._backend_dropdown.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._backend_dropdown)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._model_dropdown = LabeledDropdown.alloc().initWithLabel_items_callback_(
            "Model",
            self._ollama_models,
            self._on_model_changed,
        )
        self._model_dropdown.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._model_dropdown)

        y -= ROW_HEIGHT + TAB_ROW_GAP
        self._detail_y = y

        self._ollama_url_field = LabeledTextField.alloc().initWithLabel_callback_(
            "Ollama URL",
            self._on_ollama_url_changed,
        )
        self._ollama_url_field.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))

        login_row = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        )
        login_label = _make_label("OpenAI")
        login_row.addSubview_(login_label)

        self._login_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, 120, ROW_HEIGHT)
        )
        self._login_button.setTitle_("Login")
        self._login_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._login_delegate = _LoginButtonDelegate.alloc().initWithCallback_(
            on_openai_login
        )
        self._login_button.setTarget_(self._login_delegate)
        self._login_button.setAction_(
            objc.selector(self._login_delegate.onLoginClicked_, signature=b"v@:@")
        )
        login_row.addSubview_(self._login_button)
        self._login_row = login_row
        self._login_row.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))

        self.sync(config)

    def _show_backend_detail(self):
        self._ollama_url_field.removeFromSuperview()
        self._login_row.removeFromSuperview()

        if self._current_backend == "ollama":
            self._view.addSubview_(self._ollama_url_field)
        else:
            self._view.addSubview_(self._login_row)

    def _refresh_model_dropdown(self):
        if self._current_backend == "ollama":
            items = self._ollama_models
            current = self._model_dropdown.get_value()
        else:
            items = self._openai_models
            current = self._model_dropdown.get_value()

        self._model_dropdown.set_items(items)
        if current in items:
            self._model_dropdown.set_value(current)
        elif items:
            self._model_dropdown.set_value(items[0])

    @property
    def view(self) -> AppKit.NSView:
        return self._view

    def sync(self, config: dict):
        whisper_id = config.get("whisper_model", "mlx-community/whisper-large-v3-mlx")
        display = WHISPER_ID_TO_DISPLAY.get(whisper_id, whisper_id)
        self._whisper_dropdown.set_value(display)

        self._current_backend = config.get("postprocessor", "ollama")
        self._backend_dropdown.set_value(
            BACKEND_KEY_TO_DISPLAY.get(self._current_backend, "Ollama")
        )

        self._ollama_url_field.set_value(
            config.get("ollama_url", "http://localhost:11434")
        )

        if self._current_backend == "ollama":
            model = config.get("ollama_model", "gemma3:4b")
            if model not in self._ollama_models:
                self._ollama_models.insert(0, model)
        else:
            model = config.get("openai_model", "gpt-5.4")
            if model not in self._openai_models:
                self._openai_models = [model]

        self._refresh_model_dropdown()
        self._model_dropdown.set_value(model)
        self._show_backend_detail()

    def refresh_ollama_models(self, models: list[str]):
        self._ollama_models = merge_ollama_models(models)
        if self._current_backend == "ollama":
            self._refresh_model_dropdown()

    def refresh_openai_models(self, models: list[str]):
        self._openai_models = models
        if self._current_backend == "openai":
            self._refresh_model_dropdown()

    def update_login_status(self, logged_in: bool):
        self._login_button.setTitle_("Logged In" if logged_in else "Login")
        self._login_button.setEnabled_(not logged_in)

    def _on_whisper_changed(self, display_name: str):
        model_id = WHISPER_DISPLAY_TO_ID.get(display_name)
        if model_id:
            self._on_change("whisper_model", model_id)

    def _on_backend_changed(self, display_name: str):
        key = BACKEND_DISPLAY_TO_KEY.get(display_name)
        if not key:
            return
        self._current_backend = key
        self._refresh_model_dropdown()
        self._show_backend_detail()
        model = self._model_dropdown.get_value()
        self._on_change("postprocessor", key)
        if key == "ollama":
            self._on_change("ollama_model", model)
        else:
            self._on_change("openai_model", model)

    def _on_model_changed(self, model: str):
        if self._current_backend == "ollama":
            self._on_change("ollama_model", model)
        else:
            self._on_change("openai_model", model)

    def _on_ollama_url_changed(self, url: str):
        self._on_change("ollama_url", url)
