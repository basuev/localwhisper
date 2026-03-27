from collections.abc import Callable
from typing import Any

import AppKit
import objc

from localwhisper.settings.controls import (
    CONTROL_WIDTH,
    LABEL_WIDTH,
    ROW_HEIGHT,
    TOTAL_WIDTH,
    LabeledSliderWithCheckbox,
    SoundPicker,
    _make_label,
)
from localwhisper.settings.window import (
    CONTAINER_HEIGHT,
    TAB_PADDING_TOP,
    TAB_PADDING_X,
    TAB_ROW_GAP,
    WINDOW_WIDTH,
)

SYSTEM_DEFAULT = "System Default"
REFRESH_BTN_WIDTH = 80.0
DROPDOWN_WIDTH = CONTROL_WIDTH - REFRESH_BTN_WIDTH - 8


class _DeviceRow(AppKit.NSView):
    def initWithLabel_items_onSelect_onRefresh_(
        self, label, items, dropdown_cb, refresh_cb
    ):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(_DeviceRow, self).initWithFrame_(frame)
        if self is None:
            return None

        self._dropdown_cb = dropdown_cb
        self._refresh_cb = refresh_cb

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, DROPDOWN_WIDTH, ROW_HEIGHT), False
        )
        self._popup.addItemsWithTitles_(items)
        self._popup.setTarget_(self)
        self._popup.setAction_(
            objc.selector(self.onDropdownChanged_, signature=b"v@:@")
        )
        self.addSubview_(self._popup)

        self._refresh_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(
                LABEL_WIDTH + DROPDOWN_WIDTH + 8, 0, REFRESH_BTN_WIDTH, ROW_HEIGHT
            )
        )
        self._refresh_btn.setTitle_("Refresh")
        self._refresh_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._refresh_btn.setTarget_(self)
        self._refresh_btn.setAction_(
            objc.selector(self.onRefreshClicked_, signature=b"v@:@")
        )
        self.addSubview_(self._refresh_btn)

        return self

    def onDropdownChanged_(self, sender):
        self._dropdown_cb(sender.titleOfSelectedItem())

    def onRefreshClicked_(self, sender):
        self._refresh_cb()

    def set_value(self, value: str):
        self._popup.selectItemWithTitle_(value)

    def set_items(self, items: list[str]):
        self._popup.removeAllItems()
        self._popup.addItemsWithTitles_(items)

    def get_value(self) -> str:
        return str(self._popup.titleOfSelectedItem())


class AudioTab:
    def __init__(self, config: dict, on_change: Callable[[str, Any], None]):
        self._on_change = on_change

        self._view = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, CONTAINER_HEIGHT)
        )

        y = CONTAINER_HEIGHT - TAB_PADDING_TOP - ROW_HEIGHT

        devices = [SYSTEM_DEFAULT]
        self._device_row = _DeviceRow.alloc().initWithLabel_items_onSelect_onRefresh_(
            "Input Device",
            devices,
            self._on_device_changed,
            self._on_refresh_clicked,
        )
        self._device_row.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._device_row)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._volume = (
            LabeledSliderWithCheckbox.alloc().initWithLabel_min_max_callback_(
                "Manage Volume", 0, 100, self._on_volume_changed
            )
        )
        self._volume.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._volume)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._sound_start = SoundPicker.alloc().initWithLabel_callback_(
            "Sound Start", lambda v: self._on_change("sound_start", v)
        )
        self._sound_start.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._sound_start)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._sound_stop = SoundPicker.alloc().initWithLabel_callback_(
            "Sound Stop", lambda v: self._on_change("sound_stop", v)
        )
        self._sound_stop.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._sound_stop)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._sound_cancel = SoundPicker.alloc().initWithLabel_callback_(
            "Sound Cancel", lambda v: self._on_change("sound_cancel", v)
        )
        self._sound_cancel.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._sound_cancel)

        y -= ROW_HEIGHT + TAB_ROW_GAP

        self._sound_error = SoundPicker.alloc().initWithLabel_callback_(
            "Sound Error", lambda v: self._on_change("sound_error", v)
        )
        self._sound_error.setFrameOrigin_(AppKit.NSMakePoint(TAB_PADDING_X, y))
        self._view.addSubview_(self._sound_error)

        self.sync(config)

    @property
    def view(self) -> AppKit.NSView:
        return self._view

    def sync(self, config: dict):
        device = config.get("input_device")
        self._device_row.set_value(device if device else SYSTEM_DEFAULT)

        volume = config.get("recording_volume")
        self._volume.set_value(volume)

        self._sound_start.set_value(config.get("sound_start", ""))
        self._sound_stop.set_value(config.get("sound_stop", ""))
        self._sound_cancel.set_value(config.get("sound_cancel", ""))
        self._sound_error.set_value(config.get("sound_error", ""))

    def refresh_devices(self, devices: list[str]):
        current = self._device_row.get_value()
        items = [SYSTEM_DEFAULT] + devices
        self._device_row.set_items(items)
        if current in items:
            self._device_row.set_value(current)
        else:
            self._device_row.set_value(SYSTEM_DEFAULT)

    def _on_device_changed(self, title: str):
        value = None if title == SYSTEM_DEFAULT else title
        self._on_change("input_device", value)

    def _on_volume_changed(self, value: int | None):
        self._on_change("recording_volume", value)

    def _on_refresh_clicked(self):
        self._on_change("_refresh_devices", True)
