import threading
from collections.abc import Callable

import Quartz

ESCAPE_KEYCODE = 53


class HotkeyListener:
    """Listens for Right Option key press/release as a toggle.

    Only triggers if Right Option was pressed and released without
    any other key being pressed in between (so Option+key combos still work).

    Also handles Escape key for cancellation during recording/processing.
    """

    RIGHT_OPTION_KEYCODE = 61

    def __init__(
        self,
        callback: Callable[[], None],
        cancel_callback: Callable[[], bool],
        keycode: int | None = None,
    ):
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.keycode = keycode or self.RIGHT_OPTION_KEYCODE
        self._right_option_down = False
        self._other_key_pressed = False
        self._escape_swallowed = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            (
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
                | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            ),
            self._event_callback,
            None,
        )

        if tap is None:
            raise RuntimeError(
                "Failed to create event tap. "
                "Grant Accessibility permission in "
                "System Settings > Privacy & Security."
            )

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), run_loop_source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(tap, True)
        Quartz.CFRunLoopRun()

    def _event_callback(self, proxy, event_type, event, refcon):
        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )

        if event_type == Quartz.kCGEventFlagsChanged:
            if keycode == self.keycode:
                flags = Quartz.CGEventGetFlags(event)
                option_down = bool(flags & Quartz.kCGEventFlagMaskAlternate)

                if option_down and not self._right_option_down:
                    self._right_option_down = True
                    self._other_key_pressed = False
                elif not option_down and self._right_option_down:
                    self._right_option_down = False
                    if not self._other_key_pressed:
                        self.callback()

        elif event_type == Quartz.kCGEventKeyDown:
            if keycode == ESCAPE_KEYCODE and self.cancel_callback():
                self._escape_swallowed = True
                return None
            if self._right_option_down:
                self._other_key_pressed = True

        elif event_type == Quartz.kCGEventKeyUp:
            if keycode == ESCAPE_KEYCODE and self._escape_swallowed:
                self._escape_swallowed = False
                return None
            if self._right_option_down:
                self._other_key_pressed = True

        return event
