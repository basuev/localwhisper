from collections.abc import Callable

import AppKit
import objc

WINDOW_WIDTH = 620.0
WINDOW_HEIGHT = 350.0
BUTTON_HEIGHT = 32.0
BUTTON_WIDTH = 100.0
BUTTON_MARGIN = 12.0
LABEL_HEIGHT = 20.0
PANE_GAP = 12.0
TOP_MARGIN = 12.0


class _FeedbackDelegate(AppKit.NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_FeedbackDelegate, self).init()
        if self is None:
            return None
        self._owner = owner
        return self

    def windowShouldClose_(self, sender):
        sender.orderOut_(None)
        self._owner._do_cancel()
        return False


class FeedbackWindow:
    _instance = None

    @classmethod
    def shared(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._on_confirm: Callable[[str, str], None] | None = None
        self._on_cancel: Callable[[], None] | None = None
        self._original_text = ""
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
        self._window.setTitle_("feedback")

        self._delegate = _FeedbackDelegate.alloc().initWithOwner_(self)
        self._window.setDelegate_(self._delegate)

        content = self._window.contentView()

        bottom_bar_top = BUTTON_MARGIN + BUTTON_HEIGHT + BUTTON_MARGIN
        label_y = WINDOW_HEIGHT - TOP_MARGIN - LABEL_HEIGHT
        pane_top = label_y - 4
        pane_height = pane_top - bottom_bar_top
        pane_width = (WINDOW_WIDTH - PANE_GAP - 2 * BUTTON_MARGIN) / 2

        left_label = AppKit.NSTextField.labelWithString_("original")
        left_label.setFrame_(
            AppKit.NSMakeRect(BUTTON_MARGIN, label_y, pane_width, LABEL_HEIGHT)
        )
        content.addSubview_(left_label)

        right_label = AppKit.NSTextField.labelWithString_("corrected")
        right_label.setFrame_(
            AppKit.NSMakeRect(
                BUTTON_MARGIN + pane_width + PANE_GAP,
                label_y,
                pane_width,
                LABEL_HEIGHT,
            )
        )
        content.addSubview_(right_label)

        left_scroll = AppKit.NSTextView.scrollableTextView()
        left_scroll.setFrame_(
            AppKit.NSMakeRect(BUTTON_MARGIN, bottom_bar_top, pane_width, pane_height)
        )
        left_scroll.setBorderType_(AppKit.NSBezelBorder)
        self._original_view = left_scroll.documentView()
        self._original_view.setEditable_(False)
        self._original_view.setFont_(
            AppKit.NSFont.systemFontOfSize_(AppKit.NSFont.systemFontSize())
        )
        content.addSubview_(left_scroll)

        right_x = BUTTON_MARGIN + pane_width + PANE_GAP
        right_scroll = AppKit.NSTextView.scrollableTextView()
        right_scroll.setFrame_(
            AppKit.NSMakeRect(right_x, bottom_bar_top, pane_width, pane_height)
        )
        right_scroll.setBorderType_(AppKit.NSBezelBorder)
        self._corrected_view = right_scroll.documentView()
        self._corrected_view.setEditable_(True)
        self._corrected_view.setSelectable_(True)
        self._corrected_view.setAllowsUndo_(True)
        self._corrected_view.setRichText_(False)
        self._corrected_view.setFont_(
            AppKit.NSFont.systemFontOfSize_(AppKit.NSFont.systemFontSize())
        )
        content.addSubview_(right_scroll)

        cancel_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(BUTTON_MARGIN, BUTTON_MARGIN, BUTTON_WIDTH, BUTTON_HEIGHT)
        )
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_btn.setKeyEquivalent_("\x1b")
        cancel_btn.setTarget_(self._delegate)
        cancel_btn.setAction_(
            objc.selector(self._delegate.onCancel_, signature=b"v@:@")
        )
        content.addSubview_(cancel_btn)

        confirm_x = WINDOW_WIDTH - BUTTON_MARGIN - BUTTON_WIDTH
        confirm_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(confirm_x, BUTTON_MARGIN, BUTTON_WIDTH, BUTTON_HEIGHT)
        )
        confirm_btn.setTitle_("Confirm")
        confirm_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        confirm_btn.setKeyEquivalent_("\r")
        confirm_btn.setKeyEquivalentModifierMask_(AppKit.NSEventModifierFlagCommand)
        confirm_btn.setTarget_(self._delegate)
        confirm_btn.setAction_(
            objc.selector(self._delegate.onConfirm_, signature=b"v@:@")
        )
        content.addSubview_(confirm_btn)

    def show(
        self,
        original_text: str,
        on_confirm: Callable[[str, str], None],
        on_cancel: Callable[[], None],
    ):
        self._original_text = original_text
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        self._original_view.setString_(original_text)
        self._corrected_view.setString_(original_text)

        if not self._shown_once:
            self._window.center()
            self._shown_once = True

        self._saved_policy = AppKit.NSApp.activationPolicy()
        AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        self._window.makeKeyAndOrderFront_(None)
        self._window.makeFirstResponder_(self._corrected_view)

    def _restore_policy(self):
        if hasattr(self, "_saved_policy"):
            AppKit.NSApp.setActivationPolicy_(self._saved_policy)

    def _do_confirm(self):
        corrected = self._corrected_view.string()
        self._window.orderOut_(None)
        self._restore_policy()
        if self._on_confirm:
            self._on_confirm(self._original_text, corrected)

    def _do_cancel(self):
        self._window.orderOut_(None)
        self._restore_policy()
        if self._on_cancel:
            self._on_cancel()


_FeedbackDelegate.onConfirm_ = objc.selector(
    lambda self, sender: self._owner._do_confirm(),
    signature=b"v@:@",
)

_FeedbackDelegate.onCancel_ = objc.selector(
    lambda self, sender: self._owner._do_cancel(),
    signature=b"v@:@",
)
