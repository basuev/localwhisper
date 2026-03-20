import logging
import threading

import AppKit
import objc
import rumps

log = logging.getLogger(__name__)

import Foundation

from .clipboard import ClipboardManager
from .config import load_config
from .feedback import show_feedback
from .history import save_to_history
from .hotkey import HotkeyListener
from .postprocessor import PostProcessor
from .recorder import AudioRecorder
from .sounds import play_sound
from .transcriber import Transcriber


class _FeedbackLauncher(AppKit.NSObject):
    def initWithText_callback_(self, text, callback):
        self = objc.super(_FeedbackLauncher, self).init()
        if self is None:
            return None
        self._text = text
        self._callback = callback
        return self

    def launch_(self, _sender):
        show_feedback(self._text, self._callback)


def _make_icon(symbol_name: str, with_dot: bool = False) -> AppKit.NSImage:
    """Create a status bar icon from an SF Symbol, optionally with a red dot."""
    symbol_config = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        14, AppKit.NSFontWeightRegular, 2  # NSImageSymbolScaleMedium
    )
    image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        symbol_name, None
    )
    image = image.imageWithSymbolConfiguration_(symbol_config)

    # Make it a template image so it adapts to light/dark menu bar
    image.setTemplate_(True)

    if not with_dot:
        return image

    # Draw the image with a red dot overlay
    size = image.size()
    new_image = AppKit.NSImage.alloc().initWithSize_(size)
    new_image.lockFocus()

    image.drawInRect_fromRect_operation_fraction_(
        AppKit.NSMakeRect(0, 0, size.width, size.height),
        AppKit.NSZeroRect,
        AppKit.NSCompositingOperationSourceOver,
        1.0,
    )

    # Red dot in the top-right corner
    dot_size = 5
    dot_x = size.width - dot_size - 1
    dot_y = size.height - dot_size - 1
    dot_rect = AppKit.NSMakeRect(dot_x, dot_y, dot_size, dot_size)

    AppKit.NSColor.redColor().setFill()
    AppKit.NSBezierPath.bezierPathWithOvalInRect_(dot_rect).fill()

    new_image.unlockFocus()
    # Composite image with dot is NOT a template (to preserve the red color)
    new_image.setTemplate_(False)

    return new_image


class LocalWhisperApp(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)

        self.config = load_config()
        self.recording = False
        self.processing = False
        self._cancelled = False

        self._icon_idle = _make_icon("mic")
        self._icon_recording = _make_icon("mic.fill", with_dot=True)
        self._icon_processing = _make_icon("ellipsis.circle")

        self._set_icon(self._icon_idle)

        # Quit menu item with Cmd+Q
        quit_item = rumps.MenuItem("Quit", callback=lambda _: rumps.quit_application(), key="q")
        self.menu = [quit_item]

        self.recorder = AudioRecorder(
            sample_rate=self.config["sample_rate"],
            recording_volume=self.config["recording_volume"],
            min_audio_energy=self.config["min_audio_energy"],
            min_recording_duration=self.config["min_recording_duration"],
        )
        self.transcriber = Transcriber(self.config)
        self.postprocessor = PostProcessor(self.config)
        self.clipboard = ClipboardManager()

        self.hotkey_listener = HotkeyListener(
            callback=self._on_hotkey,
            cancel_callback=self._on_cancel,
            keycode=self.config["hotkey_keycode"],
        )
        self.hotkey_listener.start()

    def _set_icon(self, nsimage: AppKit.NSImage):
        """Set status bar icon directly from NSImage, bypassing rumps file-path logic."""
        self._icon_nsimage = nsimage
        try:
            self._nsapp.setStatusBarIcon()
        except AttributeError:
            pass

    def _on_hotkey(self):
        if self.processing:
            return

        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _on_cancel(self) -> bool:
        """Handle Escape press. Returns True if the event should be swallowed."""
        if self.recording:
            self.recording = False
            self.recorder.stop()
            self._set_icon(self._icon_idle)
            play_sound(self.config["sound_cancel"])
            return True

        if self.processing:
            self._cancelled = True
            self.processing = False
            self._set_icon(self._icon_idle)
            play_sound(self.config["sound_cancel"])
            return True

        return False

    def _start_recording(self):
        self.recording = True
        self._cancelled = False
        self._set_icon(self._icon_recording)
        play_sound(self.config["sound_start"])
        try:
            self.recorder.start()
        except Exception:
            log.exception("Failed to start recording")
            self.recording = False
            self._set_icon(self._icon_idle)
            play_sound(self.config["sound_error"])

    def _stop_recording(self):
        self.recording = False
        self.processing = True
        self._set_icon(self._icon_processing)
        play_sound(self.config["sound_stop"])
        audio_data = self.recorder.stop()

        threading.Thread(target=self._process, args=(audio_data,), daemon=True).start()

    def _process(self, audio_data: bytes):
        try:
            if not audio_data or self._cancelled:
                log.warning("Skipping processing: audio_data=%d bytes, cancelled=%s",
                            len(audio_data) if audio_data else 0, self._cancelled)
                return

            raw_text = self.transcriber.transcribe(audio_data)
            if not raw_text or self._cancelled:
                log.warning("No transcription result: raw_text=%r, cancelled=%s", raw_text, self._cancelled)
                return

            processed_text = self.postprocessor.process(raw_text)
            if self._cancelled:
                return

            self.clipboard.paste(processed_text)

            if self.config.get("feedback_enabled"):
                def on_feedback(rating, comment):
                    save_to_history(raw_text, processed_text, rating=rating, comment=comment)

                launcher = _FeedbackLauncher.alloc().initWithText_callback_(
                    processed_text, on_feedback,
                )
                launcher.performSelectorOnMainThread_withObject_waitUntilDone_(
                    b"launch:", None, False,
                )
            else:
                save_to_history(raw_text, processed_text)
        except Exception:
            log.exception("Processing failed")
        finally:
            self.processing = False
            self._cancelled = False
            self._set_icon(self._icon_idle)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    app = LocalWhisperApp()
    app.run()


if __name__ == "__main__":
    main()
