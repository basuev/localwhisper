import threading
from collections.abc import Callable

import AppKit
import Foundation


PANEL_WIDTH = 320
PANEL_HEIGHT = 140
COMMENT_FIELD_HEIGHT = 60
SCREEN_MARGIN = 16
AUTO_DISMISS_SECONDS = 5.0


class FeedbackController:
    def __init__(self, callback: Callable[[bool | None, str | None], None]):
        self._callback = callback
        self._called = False
        self._timer_cancelled = False
        self._lock = threading.Lock()

    def on_thumbs_up(self) -> None:
        self._fire(True, None)

    def on_thumbs_down(self, comment: str) -> None:
        self._fire(False, comment)

    def on_timeout(self) -> None:
        self._fire(None, None)

    def cancel_timer(self) -> None:
        self._timer_cancelled = True

    @property
    def timer_cancelled(self) -> bool:
        return self._timer_cancelled

    def _fire(self, rating: bool | None, comment: str | None) -> None:
        with self._lock:
            if self._called:
                return
            self._called = True
        self._callback(rating, comment)


class _FeedbackDelegate(AppKit.NSObject):
    def initWithController_panel_(self, controller, panel):
        self = Foundation.objc.super(_FeedbackDelegate, self).init()
        if self is None:
            return None
        self._ctrl = controller
        self._panel = panel
        self._timer = None
        self._comment_field = None
        self._submit_btn = None
        return self

    def startTimer(self):
        self._timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            AUTO_DISMISS_SECONDS, self, b"timerFired:", None, False,
        )

    def cancelTimer(self):
        self._ctrl.cancel_timer()
        if self._timer:
            self._timer.invalidate()
            self._timer = None

    def timerFired_(self, timer):
        if not self._ctrl.timer_cancelled:
            self._ctrl.on_timeout()
            self._close()

    def thumbsUp_(self, sender):
        self.cancelTimer()
        self._ctrl.on_thumbs_up()
        self._close()

    def thumbsDown_(self, sender):
        self.cancelTimer()
        if self._comment_field and not self._comment_field.isHidden():
            comment = self._comment_field.string()
            self._ctrl.on_thumbs_down(comment if comment else "")
            self._close()
            return

        content_view = self._panel.contentView()
        frame = self._panel.frame()
        new_height = frame.size.height + COMMENT_FIELD_HEIGHT + 36
        new_frame = AppKit.NSMakeRect(
            frame.origin.x,
            frame.origin.y - (new_height - frame.size.height),
            frame.size.width,
            new_height,
        )
        self._panel.setFrame_display_animate_(new_frame, True, True)

        cv_bounds = content_view.bounds()
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 40, cv_bounds.size.width - 32, COMMENT_FIELD_HEIGHT)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSBezelBorder)

        text_view = AppKit.NSTextView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, cv_bounds.size.width - 36, COMMENT_FIELD_HEIGHT)
        )
        text_view.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        text_view.setMinSize_(AppKit.NSMakeSize(0, COMMENT_FIELD_HEIGHT))
        text_view.setMaxSize_(AppKit.NSMakeSize(1e7, 1e7))
        text_view.setVerticallyResizable_(True)
        text_view.textContainer().setWidthTracksTextView_(True)
        scroll.setDocumentView_(text_view)
        content_view.addSubview_(scroll)
        self._comment_field = text_view

        submit_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(cv_bounds.size.width - 16 - 100, 8, 100, 28)
        )
        submit_btn.setTitle_("Submit")
        submit_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        submit_btn.setTarget_(self)
        submit_btn.setAction_(b"submitComment:")
        content_view.addSubview_(submit_btn)
        self._submit_btn = submit_btn

        self._panel.makeFirstResponder_(text_view)

    def submitComment_(self, sender):
        comment = self._comment_field.string() if self._comment_field else ""
        self._ctrl.on_thumbs_down(comment if comment else "")
        self._close()

    def mouseEntered_(self, event):
        self.cancelTimer()

    def _close(self):
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._panel.orderOut_(None)


def show_feedback(processed_text: str, callback: Callable[[bool | None, str | None], None]) -> None:
    ctrl = FeedbackController(callback)

    screen = AppKit.NSScreen.mainScreen()
    screen_frame = screen.visibleFrame()
    panel_x = screen_frame.origin.x + screen_frame.size.width - PANEL_WIDTH - SCREEN_MARGIN
    panel_y = screen_frame.origin.y + screen_frame.size.height - PANEL_HEIGHT - SCREEN_MARGIN

    panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        AppKit.NSMakeRect(panel_x, panel_y, PANEL_WIDTH, PANEL_HEIGHT),
        AppKit.NSWindowStyleMaskTitled
        | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskNonactivatingPanel
        | AppKit.NSWindowStyleMaskUtilityWindow,
        AppKit.NSBackingStoreBuffered,
        False,
    )
    panel.setLevel_(AppKit.NSFloatingWindowLevel)
    panel.setHidesOnDeactivate_(False)
    panel.setTitle_("Feedback")

    content = panel.contentView()
    bounds = content.bounds()

    label = AppKit.NSTextField.alloc().initWithFrame_(
        AppKit.NSMakeRect(16, bounds.size.height - 60, bounds.size.width - 32, 44)
    )
    label.setStringValue_(processed_text[:200])
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    label.setMaximumNumberOfLines_(2)
    label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
    content.addSubview_(label)

    delegate = _FeedbackDelegate.alloc().initWithController_panel_(ctrl, panel)

    btn_up = AppKit.NSButton.alloc().initWithFrame_(
        AppKit.NSMakeRect(16, 16, 80, 32)
    )
    btn_up.setTitle_("\U0001f44d")
    btn_up.setBezelStyle_(AppKit.NSBezelStyleRounded)
    btn_up.setTarget_(delegate)
    btn_up.setAction_(b"thumbsUp:")
    content.addSubview_(btn_up)

    btn_down = AppKit.NSButton.alloc().initWithFrame_(
        AppKit.NSMakeRect(104, 16, 80, 32)
    )
    btn_down.setTitle_("\U0001f44e")
    btn_down.setBezelStyle_(AppKit.NSBezelStyleRounded)
    btn_down.setTarget_(delegate)
    btn_down.setAction_(b"thumbsDown:")
    content.addSubview_(btn_down)

    tracking_area = AppKit.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
        bounds,
        AppKit.NSTrackingMouseEnteredAndMoved | AppKit.NSTrackingActiveAlways,
        delegate,
        None,
    )
    content.addTrackingArea_(tracking_area)

    panel.orderFrontRegardless()
    delegate.startTimer()

    panel._feedbackDelegate = delegate
