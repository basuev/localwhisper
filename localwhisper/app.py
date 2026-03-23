import logging
import threading

import AppKit
import rumps

log = logging.getLogger(__name__)

from . import oauth
from .clipboard import ClipboardManager
from .config import load_config, save_config
from .history import save_to_history
from .hotkey import HotkeyListener
from .models import fetch_ollama_models, load_codex_models
from .postprocessor import PostProcessor
from .recorder import AudioRecorder
from .sounds import play_sound
from .transcriber import Transcriber

SPEECH_LANGUAGES = [
    ("ru", "Russian"),
    ("en", "English"),
    ("de", "German"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("uk", "Ukrainian"),
    ("pl", "Polish"),
]

TRANSLATE_LANGUAGES = [
    "Off",
    "Russian",
    "English",
    "German",
    "French",
    "Spanish",
    "Japanese",
    "Chinese",
    "Korean",
]


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

        self._current_backend = self.config.get("postprocessor", "ollama")
        if self._current_backend == "ollama":
            self._current_model = self.config["ollama_model"]
        else:
            self._current_model = self.config.get("openai_model", "codex-gpt-5.4")

        self._model_menu = rumps.MenuItem(self._model_menu_title())
        self._local_menu = rumps.MenuItem("Local")
        self._openai_menu = rumps.MenuItem("OpenAI")

        token = oauth.load_token()
        login_title = "Logged in" if token else "Login"
        self._openai_login_item = rumps.MenuItem(login_title, callback=self._on_openai_login)
        self._openai_menu[self._openai_login_item.title] = self._openai_login_item

        self._model_menu[self._local_menu.title] = self._local_menu
        self._model_menu[self._openai_menu.title] = self._openai_menu

        current_lang_name = next(
            (name for code, name in SPEECH_LANGUAGES if code == self.config["language"]),
            self.config["language"],
        )
        self._speech_lang_menu = rumps.MenuItem(f"Speech: {current_lang_name}")
        for code, name in SPEECH_LANGUAGES:
            item = rumps.MenuItem(name, callback=self._make_speech_lang_callback(code, name))
            if code == self.config["language"]:
                item.state = 1
            self._speech_lang_menu[name] = item

        current_translate = self.config.get("translate_to")
        translate_label = current_translate if current_translate else "Off"
        self._translate_menu = rumps.MenuItem(f"Translate: {translate_label}")
        for lang in TRANSLATE_LANGUAGES:
            item = rumps.MenuItem(lang, callback=self._make_translate_callback(lang))
            if lang == "Off" and not current_translate:
                item.state = 1
            elif lang == current_translate:
                item.state = 1
            self._translate_menu[lang] = item

        quit_item = rumps.MenuItem("Quit", callback=lambda _: rumps.quit_application(), key="q")
        self.menu = [self._model_menu, self._speech_lang_menu, self._translate_menu, None, quit_item]

        self._populate_default_models()
        threading.Thread(target=self._refresh_models, daemon=True).start()

        self.recorder = AudioRecorder(
            sample_rate=self.config["sample_rate"],
            recording_volume=self.config["recording_volume"],
            min_audio_energy=self.config["min_audio_energy"],
            min_recording_duration=self.config["min_recording_duration"],
            input_device=self.config["input_device"],
        )
        self.transcriber = Transcriber(self.config)
        threading.Thread(target=self.transcriber.preload, daemon=True).start()
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

    def _model_menu_title(self) -> str:
        backend_label = "Local" if self._current_backend == "ollama" else "OpenAI"
        return f"Model: {backend_label} ({self._current_model})"

    def _populate_default_models(self):
        default_model = self.config["ollama_model"]
        item = rumps.MenuItem(default_model, callback=self._make_model_callback("ollama", default_model))
        if self._current_backend == "ollama" and self._current_model == default_model:
            item.state = 1
        self._local_menu[default_model] = item

        codex_models = load_codex_models()
        openai_models = codex_models if codex_models else [self.config.get("openai_model", "codex-gpt-5.4")]
        for name in openai_models:
            item = rumps.MenuItem(name, callback=self._make_model_callback("openai", name))
            if self._current_backend == "openai" and self._current_model == name:
                item.state = 1
            self._openai_menu[name] = item

    def _refresh_models(self):
        ollama_models = fetch_ollama_models(self.config["ollama_url"])
        if ollama_models:
            self._local_menu.clear()
            for name in ollama_models:
                item = rumps.MenuItem(name, callback=self._make_model_callback("ollama", name))
                if self._current_backend == "ollama" and self._current_model == name:
                    item.state = 1
                self._local_menu[name] = item

    def _make_model_callback(self, backend: str, model: str):
        def callback(_):
            self._select_model(backend, model)
        return callback

    def _select_model(self, backend: str, model: str):
        for menu in (self._local_menu, self._openai_menu):
            for key in menu:
                if isinstance(menu[key], rumps.MenuItem):
                    menu[key].state = 0

        self._current_backend = backend
        self._current_model = model
        self.postprocessor.switch(backend, model)

        submenu = self._local_menu if backend == "ollama" else self._openai_menu
        if model in submenu:
            submenu[model].state = 1

        self._model_menu.title = self._model_menu_title()
        model_key = "ollama_model" if backend == "ollama" else "openai_model"
        save_config({"postprocessor": backend, model_key: model})

    def _make_speech_lang_callback(self, code: str, name: str):
        def callback(_):
            self._select_speech_language(code, name)
        return callback

    def _select_speech_language(self, code: str, name: str):
        for key in self._speech_lang_menu:
            if isinstance(self._speech_lang_menu[key], rumps.MenuItem):
                self._speech_lang_menu[key].state = 0
        self.transcriber.language = code
        if name in self._speech_lang_menu:
            self._speech_lang_menu[name].state = 1
        self._speech_lang_menu.title = f"Speech: {name}"
        save_config({"language": code})

    def _make_translate_callback(self, language: str):
        def callback(_):
            self._select_translate(language)
        return callback

    def _select_translate(self, language: str):
        for key in self._translate_menu:
            if isinstance(self._translate_menu[key], rumps.MenuItem):
                self._translate_menu[key].state = 0
        if language == "Off":
            self.postprocessor.set_translate_to(None)
            self._translate_menu.title = "Translate: Off"
            if "Off" in self._translate_menu:
                self._translate_menu["Off"].state = 1
            save_config({"translate_to": None})
        else:
            self.postprocessor.set_translate_to(language)
            self._translate_menu.title = f"Translate: {language}"
            if language in self._translate_menu:
                self._translate_menu[language].state = 1
            save_config({"translate_to": language})

    def _on_openai_login(self, _):
        self._openai_login_item.title = "Logging in..."
        self._openai_login_item.set_callback(None)

        def do_login():
            if oauth.login():
                self._openai_login_item.title = "Logged in"
                threading.Thread(target=self._refresh_models, daemon=True).start()
            else:
                self._openai_login_item.title = "Login failed"
            self._openai_login_item.set_callback(self._on_openai_login)

        threading.Thread(target=do_login, daemon=True).start()

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
