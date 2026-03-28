from collections.abc import Callable
from typing import Any

import AppKit

from localwhisper.settings.controls import (
    ROW_HEIGHT,
    LabeledTextField,
    LabeledToggle,
)
from localwhisper.settings.window import (
    CONTAINER_HEIGHT,
    TAB_PADDING_TOP,
    TAB_PADDING_X,
    TAB_ROW_GAP,
    WINDOW_WIDTH,
)


class AdvancedTab:
    def __init__(self, config: dict, on_change: Callable[[str, Any], None]):
        self._on_change = on_change

        self._view = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, CONTAINER_HEIGHT)
        )

        y = CONTAINER_HEIGHT - TAB_PADDING_TOP - ROW_HEIGHT

        self._postprocess = LabeledToggle.alloc().initWithLabel_callback_(
            "Post-Processing",
            lambda val: self._on_change("postprocess", val),
        )
        self._postprocess.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._postprocess)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._streaming = LabeledToggle.alloc().initWithLabel_callback_(
            "Streaming",
            lambda val: self._on_change("streaming", val),
        )
        self._streaming.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._streaming)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._idle_timeout = LabeledTextField.alloc().initWithLabel_callback_(
            "Idle Timeout (sec)",
            lambda val: self._on_change("model_idle_timeout", int(val)),
        )
        self._idle_timeout.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._idle_timeout)

        self.sync(config)

    @property
    def view(self) -> AppKit.NSView:
        return self._view

    def sync(self, config: dict):
        self._postprocess.set_value(config.get("postprocess", True))
        self._streaming.set_value(config.get("streaming", True))
        self._idle_timeout.set_value(str(config.get("model_idle_timeout", 300)))
