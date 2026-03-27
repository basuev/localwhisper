import time

import AppKit
import Quartz


class ClipboardManager:
    def paste(self, text: str):
        pasteboard = AppKit.NSPasteboard.generalPasteboard()

        # Save current clipboard
        old_contents = self._get_clipboard()

        # Set new text
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)

        # Simulate Cmd+V
        self._simulate_paste()

        # Wait for paste to complete, then restore
        time.sleep(0.05)

        # Restore previous clipboard if it was different
        if old_contents is not None:
            pasteboard.clearContents()
            pasteboard.setString_forType_(old_contents, AppKit.NSPasteboardTypeString)

    def _get_clipboard(self) -> str | None:
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        return pasteboard.stringForType_(AppKit.NSPasteboardTypeString)

    def _simulate_paste(self):
        # Create Cmd+V key down event
        source = Quartz.CGEventSourceCreate(
            Quartz.kCGEventSourceStateCombinedSessionState
        )

        # Key code 9 = 'v'
        cmd_v_down = Quartz.CGEventCreateKeyboardEvent(source, 9, True)
        cmd_v_up = Quartz.CGEventCreateKeyboardEvent(source, 9, False)

        # Add Cmd modifier
        Quartz.CGEventSetFlags(cmd_v_down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventSetFlags(cmd_v_up, Quartz.kCGEventFlagMaskCommand)

        # Post events
        Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, cmd_v_down)
        Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, cmd_v_up)
