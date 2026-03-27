import os
from collections.abc import Callable

import AppKit
import objc

LABEL_WIDTH = 120.0
CONTROL_WIDTH = 300.0
ROW_HEIGHT = 24.0
TOTAL_WIDTH = LABEL_WIDTH + CONTROL_WIDTH


def _make_label(text: str) -> AppKit.NSTextField:
    label = AppKit.NSTextField.labelWithString_(text)
    label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
    label.setAlignment_(AppKit.NSTextAlignmentRight)
    label.setFrame_(AppKit.NSMakeRect(0, 0, LABEL_WIDTH - 8, ROW_HEIGHT))
    return label


class _TextFieldDelegate(AppKit.NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(_TextFieldDelegate, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def controlTextDidEndEditing_(self, notification):
        field = notification.object()
        self._callback(field.stringValue())


class LabeledDropdown(AppKit.NSView):
    def initWithLabel_items_callback_(self, label, items, callback):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(LabeledDropdown, self).initWithFrame_(frame)
        if self is None:
            return None

        self._callback = callback

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, CONTROL_WIDTH, ROW_HEIGHT), False
        )
        self._popup.addItemsWithTitles_(items)
        self._popup.setTarget_(self)
        self._popup.setAction_(
            objc.selector(self.onDropdownChanged_, signature=b"v@:@")
        )
        self.addSubview_(self._popup)

        return self

    def onDropdownChanged_(self, sender):
        self._callback(sender.titleOfSelectedItem())

    def set_value(self, value: str):
        self._popup.selectItemWithTitle_(value)

    def set_items(self, items: list[str]):
        self._popup.removeAllItems()
        self._popup.addItemsWithTitles_(items)

    def get_value(self) -> str:
        return str(self._popup.titleOfSelectedItem())


class LabeledToggle(AppKit.NSView):
    def initWithLabel_callback_(self, label, callback):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(LabeledToggle, self).initWithFrame_(frame)
        if self is None:
            return None

        self._callback = callback

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._checkbox = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, CONTROL_WIDTH, ROW_HEIGHT)
        )
        self._checkbox.setButtonType_(AppKit.NSButtonTypeSwitch)
        self._checkbox.setTitle_("")
        self._checkbox.setTarget_(self)
        self._checkbox.setAction_(
            objc.selector(self.onToggleChanged_, signature=b"v@:@")
        )
        self.addSubview_(self._checkbox)

        return self

    def onToggleChanged_(self, sender):
        self._callback(sender.state() == AppKit.NSControlStateValueOn)

    def set_value(self, value: bool):
        self._checkbox.setState_(
            AppKit.NSControlStateValueOn if value else AppKit.NSControlStateValueOff
        )

    def get_value(self) -> bool:
        return self._checkbox.state() == AppKit.NSControlStateValueOn


class LabeledTextField(AppKit.NSView):
    def initWithLabel_callback_(self, label, callback):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(LabeledTextField, self).initWithFrame_(frame)
        if self is None:
            return None

        self._callback = callback

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._field = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, CONTROL_WIDTH, ROW_HEIGHT)
        )
        self._delegate = _TextFieldDelegate.alloc().initWithCallback_(callback)
        self._field.setDelegate_(self._delegate)
        self.addSubview_(self._field)

        return self

    def set_value(self, value: str):
        self._field.setStringValue_(value)

    def get_value(self) -> str:
        return str(self._field.stringValue())


class LabeledSliderWithCheckbox(AppKit.NSView):
    def initWithLabel_min_max_callback_(self, label, min_val, max_val, callback):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(LabeledSliderWithCheckbox, self).initWithFrame_(frame)
        if self is None:
            return None

        self._callback = callback
        self._min_val = min_val
        self._max_val = max_val

        checkbox_size = 20.0
        gap = 8.0
        slider_width = CONTROL_WIDTH - checkbox_size - gap

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._slider = AppKit.NSSlider.alloc().initWithFrame_(
            AppKit.NSMakeRect(LABEL_WIDTH, 0, slider_width, ROW_HEIGHT)
        )
        self._slider.setMinValue_(float(min_val))
        self._slider.setMaxValue_(float(max_val))
        self._slider.setTarget_(self)
        self._slider.setAction_(objc.selector(self.onSliderChanged_, signature=b"v@:@"))
        self.addSubview_(self._slider)

        self._checkbox = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(
                LABEL_WIDTH + slider_width + gap, 0, checkbox_size, ROW_HEIGHT
            )
        )
        self._checkbox.setButtonType_(AppKit.NSButtonTypeSwitch)
        self._checkbox.setTitle_("")
        self._checkbox.setTarget_(self)
        self._checkbox.setAction_(
            objc.selector(self.onCheckboxChanged_, signature=b"v@:@")
        )
        self.addSubview_(self._checkbox)

        return self

    def onCheckboxChanged_(self, sender):
        enabled = sender.state() == AppKit.NSControlStateValueOn
        self._slider.setEnabled_(enabled)
        if enabled:
            self._callback(int(self._slider.intValue()))
        else:
            self._callback(None)

    def onSliderChanged_(self, sender):
        self._callback(int(sender.intValue()))

    def set_value(self, value: int | None):
        if value is None:
            self._checkbox.setState_(AppKit.NSControlStateValueOff)
            self._slider.setEnabled_(False)
        else:
            self._checkbox.setState_(AppKit.NSControlStateValueOn)
            self._slider.setEnabled_(True)
            self._slider.setIntValue_(value)

    def get_value(self) -> int | None:
        if self._checkbox.state() != AppKit.NSControlStateValueOn:
            return None
        return int(self._slider.intValue())


_system_sounds_cache: list[str] | None = None


def _list_system_sounds() -> list[str]:
    global _system_sounds_cache
    if _system_sounds_cache is not None:
        return _system_sounds_cache
    sounds_dir = "/System/Library/Sounds"
    try:
        files = sorted(os.listdir(sounds_dir))
    except OSError:
        return []
    _system_sounds_cache = [
        os.path.join(sounds_dir, f) for f in files if not f.startswith(".")
    ]
    return _system_sounds_cache


class SoundPicker(AppKit.NSView):
    def initWithLabel_callback_(self, label, callback):
        frame = AppKit.NSMakeRect(0, 0, TOTAL_WIDTH, ROW_HEIGHT)
        self = objc.super(SoundPicker, self).initWithFrame_(frame)
        if self is None:
            return None

        self._callback = callback
        self._sounds = _list_system_sounds()

        checkbox_size = 20.0
        preview_width = 56.0
        gap = 8.0
        dropdown_width = CONTROL_WIDTH - checkbox_size - preview_width - gap * 2
        x = LABEL_WIDTH

        self._label = _make_label(label)
        self.addSubview_(self._label)

        self._popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AppKit.NSMakeRect(x, 0, dropdown_width, ROW_HEIGHT), False
        )
        display_names = [os.path.splitext(os.path.basename(p))[0] for p in self._sounds]
        self._popup.addItemsWithTitles_(display_names)
        self._popup.setTarget_(self)
        self._popup.setAction_(objc.selector(self.onSoundSelected_, signature=b"v@:@"))
        self.addSubview_(self._popup)
        x += dropdown_width + gap

        self._checkbox = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(x, 0, checkbox_size, ROW_HEIGHT)
        )
        self._checkbox.setButtonType_(AppKit.NSButtonTypeSwitch)
        self._checkbox.setTitle_("")
        self._checkbox.setTarget_(self)
        self._checkbox.setAction_(
            objc.selector(self.onCheckboxChanged_, signature=b"v@:@")
        )
        self.addSubview_(self._checkbox)
        x += checkbox_size + gap

        self._preview_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(x, 0, preview_width, ROW_HEIGHT)
        )
        self._preview_btn.setTitle_("Play")
        self._preview_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._preview_btn.setTarget_(self)
        self._preview_btn.setAction_(
            objc.selector(self.onPreviewClicked_, signature=b"v@:@")
        )
        self.addSubview_(self._preview_btn)

        return self

    def onCheckboxChanged_(self, sender):
        enabled = sender.state() == AppKit.NSControlStateValueOn
        self._popup.setEnabled_(enabled)
        self._preview_btn.setEnabled_(enabled)
        if enabled:
            idx = self._popup.indexOfSelectedItem()
            if 0 <= idx < len(self._sounds):
                self._callback(self._sounds[idx])
        else:
            self._callback("")

    def onSoundSelected_(self, sender):
        idx = sender.indexOfSelectedItem()
        if 0 <= idx < len(self._sounds):
            self._callback(self._sounds[idx])

    def onPreviewClicked_(self, sender):
        idx = self._popup.indexOfSelectedItem()
        if 0 <= idx < len(self._sounds):
            sound = AppKit.NSSound.alloc().initWithContentsOfFile_byReference_(
                self._sounds[idx], True
            )
            if sound:
                sound.play()

    def set_value(self, value: str):
        if not value:
            self._checkbox.setState_(AppKit.NSControlStateValueOff)
            self._popup.setEnabled_(False)
            self._preview_btn.setEnabled_(False)
            return
        self._checkbox.setState_(AppKit.NSControlStateValueOn)
        self._popup.setEnabled_(True)
        self._preview_btn.setEnabled_(True)
        for i, path in enumerate(self._sounds):
            if path == value:
                self._popup.selectItemAtIndex_(i)
                return
        name = os.path.splitext(os.path.basename(value))[0]
        self._popup.selectItemWithTitle_(name)

    def get_value(self) -> str:
        if self._checkbox.state() != AppKit.NSControlStateValueOn:
            return ""
        idx = self._popup.indexOfSelectedItem()
        if 0 <= idx < len(self._sounds):
            return self._sounds[idx]
        return ""
