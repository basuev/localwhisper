from collections.abc import Callable
from typing import Any

import AppKit
import objc

WINDOW_WIDTH = 520.0
WINDOW_HEIGHT = 450.0
SEGMENTED_HEIGHT = 28.0
SEGMENTED_TOP_MARGIN = 12.0
SEGMENTED_BOTTOM_MARGIN = 8.0
TAB_LABELS = ["General", "Models", "Audio", "Advanced"]
CONTAINER_HEIGHT = (
    WINDOW_HEIGHT - SEGMENTED_HEIGHT - SEGMENTED_TOP_MARGIN - SEGMENTED_BOTTOM_MARGIN
)
TAB_PADDING_X = 20.0
TAB_PADDING_TOP = 20.0
TAB_ROW_GAP = 8.0


class _WindowDelegate(AppKit.NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_WindowDelegate, self).init()
        if self is None:
            return None
        self._owner = owner
        return self

    def windowShouldClose_(self, sender):
        sender.orderOut_(None)
        return False


class SettingsWindow:
    _instance = None

    @classmethod
    def shared(cls, config=None, on_change=None):
        if cls._instance is None:
            if config is None or on_change is None:
                raise ValueError("config and on_change required for first creation")
            cls._instance = cls(config, on_change)
        return cls._instance

    def __init__(self, config: dict, on_change: Callable[[str, Any], None]):
        self._on_change = on_change
        self._tab_views: list[AppKit.NSView | None] = [None, None, None, None]
        self._current_tab = 0
        self._shown_once = False

        content_rect = AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        style = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
        self._window = (
            AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                content_rect,
                style,
                AppKit.NSBackingStoreBuffered,
                False,
            )
        )
        self._window.setTitle_("LocalWhisper Preferences")

        self._delegate = _WindowDelegate.alloc().initWithOwner_(self)
        self._window.setDelegate_(self._delegate)

        content = self._window.contentView()

        seg_width = WINDOW_WIDTH - 40
        seg_x = (WINDOW_WIDTH - seg_width) / 2
        seg_y = WINDOW_HEIGHT - SEGMENTED_HEIGHT - SEGMENTED_TOP_MARGIN
        self._segmented = AppKit.NSSegmentedControl.alloc().initWithFrame_(
            AppKit.NSMakeRect(seg_x, seg_y, seg_width, SEGMENTED_HEIGHT)
        )
        self._segmented.setSegmentCount_(len(TAB_LABELS))
        for i, label in enumerate(TAB_LABELS):
            self._segmented.setLabel_forSegment_(label, i)
            self._segmented.setWidth_forSegment_(seg_width / len(TAB_LABELS), i)
        self._segmented.setSelectedSegment_(0)
        self._segmented.setSegmentStyle_(AppKit.NSSegmentStyleAutomatic)
        self._segmented.setTarget_(self._delegate)
        self._segmented.setAction_(
            objc.selector(self._delegate.onTabChanged_, signature=b"v@:@")
        )
        content.addSubview_(self._segmented)

        container_y = 0.0
        container_h = seg_y - SEGMENTED_BOTTOM_MARGIN
        self._container = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, container_y, WINDOW_WIDTH, container_h)
        )
        content.addSubview_(self._container)

    def show(self):
        if not self._shown_once:
            self._window.center()
            self._shown_once = True
        self._window.orderFrontRegardless()
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def set_tab_view(self, index: int, view: AppKit.NSView):
        self._tab_views[index] = view
        if index == self._current_tab:
            self._switch_to_tab(index)

    def sync_from_config(self, config: dict):
        for view in self._tab_views:
            if view is not None and hasattr(view, "sync"):
                view.sync(config)

    def _switch_to_tab(self, index: int):
        for sub in list(self._container.subviews()):
            sub.removeFromSuperview()
        self._current_tab = index
        view = self._tab_views[index]
        if view is not None:
            self._container.addSubview_(view)

    def _on_tab_changed(self, sender):
        idx = sender.selectedSegment()
        self._switch_to_tab(idx)


_WindowDelegate.onTabChanged_ = objc.selector(
    lambda self, sender: self._owner._on_tab_changed(sender),
    signature=b"v@:@",
)
