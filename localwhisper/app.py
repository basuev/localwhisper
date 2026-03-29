import logging
import math
import sys
import threading

import AppKit
import rumps
from PyObjCTools.AppHelper import callAfter

from . import focus, oauth
from .clipboard import ClipboardManager
from .config import load_config, save_config
from .constants import (
    OLLAMA_MODELS,
    SPEECH_LANGUAGES,
    TRANSLATE_LANGUAGES,
    WHISPER_MODELS,
)
from .engine import LocalWhisperEngine
from .events import (
    Cancelled,
    PostProcessingDone,
    PostProcessingFailed,
    RecordingDone,
    RecordingFailed,
    RecordingStarted,
    TranscriptionFailed,
)
from .history import save_to_history
from .hotkey import HotkeyListener
from .models import fetch_ollama_models, load_codex_models
from .overlay import AudioOverlay
from .recorder import list_input_devices
from .settings.tabs.advanced import AdvancedTab
from .settings.tabs.audio import AudioTab
from .settings.tabs.general import GeneralTab
from .settings.tabs.models import ModelsTab
from .settings.window import SettingsWindow
from .sounds import play_sound

log = logging.getLogger(__name__)


_ICON_SIZE = 18.0
_ICON_BLOB_RADIUS = 7.0
_ICON_N_POINTS = 64


def _make_blob_icon() -> AppKit.NSImage:
    cx = _ICON_SIZE / 2
    cy = _ICON_SIZE / 2
    t = 1.0
    points = []
    for i in range(_ICON_N_POINTS):
        theta = 2 * math.pi * i / _ICON_N_POINTS
        deform = (
            math.sin(3 * theta + t * 2.0) * 0.12
            + math.sin(5 * theta - t * 1.5) * 0.08
            + math.sin(7 * theta + t * 0.9) * 0.05
        )
        r = _ICON_BLOB_RADIUS * (1.0 + deform)
        points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))

    n = len(points)
    path = AppKit.NSBezierPath.bezierPath()
    path.moveToPoint_(AppKit.NSMakePoint(*points[0]))
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        cp1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        cp2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.curveToPoint_controlPoint1_controlPoint2_(
            AppKit.NSMakePoint(*p2),
            AppKit.NSMakePoint(*cp1),
            AppKit.NSMakePoint(*cp2),
        )
    path.closePath()

    image = AppKit.NSImage.alloc().initWithSize_(
        AppKit.NSMakeSize(_ICON_SIZE, _ICON_SIZE)
    )
    image.lockFocus()
    AppKit.NSColor.blackColor().setFill()
    path.fill()
    image.unlockFocus()
    image.setTemplate_(True)
    return image


class LocalWhisperApp(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)

        self.config = load_config()
        self._recording_source_app = None
        self.clipboard = ClipboardManager()
        self._settings_window = None
        self._general_tab = None
        self._models_tab = None
        self._audio_tab = None
        self._advanced_tab = None

        self._set_icon(_make_blob_icon())

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
        self._openai_login_item = rumps.MenuItem(
            login_title, callback=self._on_openai_login
        )
        self._openai_menu[self._openai_login_item.title] = self._openai_login_item

        self._model_menu[self._local_menu.title] = self._local_menu
        self._model_menu[self._openai_menu.title] = self._openai_menu

        current_lang_name = next(
            (
                name
                for code, name in SPEECH_LANGUAGES
                if code == self.config["language"]
            ),
            self.config["language"],
        )
        self._speech_lang_menu = rumps.MenuItem(f"Speech: {current_lang_name}")
        for code, name in SPEECH_LANGUAGES:
            item = rumps.MenuItem(
                name, callback=self._make_speech_lang_callback(code, name)
            )
            if code == self.config["language"]:
                item.state = 1
            self._speech_lang_menu[name] = item

        current_translate = self.config.get("translate_to")
        translate_label = current_translate if current_translate else "Off"
        self._translate_menu = rumps.MenuItem(f"Translate: {translate_label}")
        for lang in TRANSLATE_LANGUAGES:
            item = rumps.MenuItem(lang, callback=self._make_translate_callback(lang))
            if lang == "Off" and not current_translate or lang == current_translate:
                item.state = 1
            self._translate_menu[lang] = item

        current_device = self.config.get("input_device")
        device_label = current_device if current_device else "system default"
        self._device_menu = rumps.MenuItem(f"Input: {device_label}")
        self._populate_devices()

        self._whisper_menu = rumps.MenuItem("Whisper model")
        self._populate_whisper_models()

        pp_state = self.config.get("postprocess", True)
        self._postprocess_item = rumps.MenuItem(
            "Post-processing",
            callback=self._toggle_postprocess,
        )
        self._postprocess_item.state = 1 if pp_state else 0

        streaming_state = self.config.get("streaming", True)
        self._streaming_item = rumps.MenuItem(
            "Streaming",
            callback=self._toggle_streaming,
        )
        self._streaming_item.state = 1 if streaming_state else 0

        current_theme = self.config.get("blob_theme", "dark")
        self._theme_item = rumps.MenuItem(
            "Light blob",
            callback=self._toggle_theme,
        )
        self._theme_item.state = 1 if current_theme == "light" else 0

        self._preferences_item = rumps.MenuItem(
            "Preferences...", callback=self._on_preferences, key=","
        )

        quit_item = rumps.MenuItem(
            "Quit", callback=lambda _: rumps.quit_application(), key="q"
        )
        self.menu = [
            self._speech_lang_menu,
            self._translate_menu,
            None,
            self._postprocess_item,
            self._streaming_item,
            None,
            self._preferences_item,
            None,
            quit_item,
        ]

        self._populate_default_models()
        threading.Thread(target=self._refresh_models, daemon=True).start()

        self.engine = LocalWhisperEngine(self.config)
        self._overlay = AudioOverlay(theme=self.config.get("blob_theme", "dark"))
        self.engine.set_amplitude_callback(self._overlay.update_amplitude)

        self.engine.on(RecordingStarted, self._on_recording_started)
        self.engine.on(RecordingFailed, self._on_recording_failed)
        self.engine.on(RecordingDone, self._on_recording_done)
        self.engine.on(TranscriptionFailed, self._on_transcription_failed)
        self.engine.on(PostProcessingDone, self._on_post_processing_done)
        self.engine.on(PostProcessingFailed, self._on_post_processing_failed)
        self.engine.on(Cancelled, self._on_cancelled)

        threading.Thread(target=self.engine._transcriber.preload, daemon=True).start()
        log.info(
            "Post-processing model: %s / %s", self._current_backend, self._current_model
        )

        self.hotkey_listener = HotkeyListener(
            callback=self._on_hotkey,
            cancel_callback=self._on_cancel,
            keycode=self.config["hotkey_keycode"],
            feedback_callback=self._on_feedback,
            double_click_timeout_ms=self.config.get(
                "feedback_double_click_timeout", 300
            ),
        )
        self.hotkey_listener.start()

    def _set_icon(self, nsimage: AppKit.NSImage):
        if threading.current_thread() is not threading.main_thread():
            callAfter(self._set_icon, nsimage)
            return
        self._icon_nsimage = nsimage
        import contextlib

        with contextlib.suppress(AttributeError):
            self._nsapp.setStatusBarIcon()

    def _model_menu_title(self) -> str:
        backend_label = "Local" if self._current_backend == "ollama" else "OpenAI"
        return f"Model: {backend_label} ({self._current_model})"

    def _populate_default_models(self):
        seen = set()
        for model_id, _ in OLLAMA_MODELS:
            if model_id not in seen:
                seen.add(model_id)
                item = rumps.MenuItem(
                    model_id,
                    callback=self._make_model_callback("ollama", model_id),
                )
                if (
                    self._current_backend == "ollama"
                    and self._current_model == model_id
                ):
                    item.state = 1
                self._local_menu[model_id] = item

        current = self.config["ollama_model"]
        if current not in seen:
            item = rumps.MenuItem(
                current, callback=self._make_model_callback("ollama", current)
            )
            if self._current_backend == "ollama" and self._current_model == current:
                item.state = 1
            self._local_menu[current] = item

        codex_models = load_codex_models()
        openai_models = (
            codex_models
            if codex_models
            else [self.config.get("openai_model", "codex-gpt-5.4")]
        )
        for name in openai_models:
            item = rumps.MenuItem(
                name, callback=self._make_model_callback("openai", name)
            )
            if self._current_backend == "openai" and self._current_model == name:
                item.state = 1
            self._openai_menu[name] = item

    def _refresh_models(self):
        ollama_models = fetch_ollama_models(self.config["ollama_url"])
        if ollama_models:
            recommended = [mid for mid, _ in OLLAMA_MODELS]
            seen = set(ollama_models)
            all_models = ollama_models + [r for r in recommended if r not in seen]
            self._local_menu.clear()
            for name in all_models:
                item = rumps.MenuItem(
                    name, callback=self._make_model_callback("ollama", name)
                )
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
        self.engine.update_config(
            {
                "postprocessor": backend,
                "ollama_model" if backend == "ollama" else "openai_model": model,
            }
        )

        submenu = self._local_menu if backend == "ollama" else self._openai_menu
        if model in submenu:
            submenu[model].state = 1

        self._model_menu.title = self._model_menu_title()
        log.info("Switched post-processing model: %s / %s", backend, model)
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
        self.config["language"] = code
        self.engine.update_config({"language": code})
        if name in self._speech_lang_menu:
            self._speech_lang_menu[name].state = 1
        self._speech_lang_menu.title = f"Speech: {name}"
        save_config({"language": code})
        if self._general_tab:
            self._general_tab.sync(self.config)

    def _make_translate_callback(self, language: str):
        def callback(_):
            self._select_translate(language)

        return callback

    def _select_translate(self, language: str):
        for key in self._translate_menu:
            if isinstance(self._translate_menu[key], rumps.MenuItem):
                self._translate_menu[key].state = 0
        if language == "Off":
            self.config["translate_to"] = None
            self.engine.update_config({"translate_to": None})
            self._translate_menu.title = "Translate: Off"
            if "Off" in self._translate_menu:
                self._translate_menu["Off"].state = 1
            save_config({"translate_to": None})
        else:
            self.config["translate_to"] = language
            self.engine.update_config({"translate_to": language})
            self._translate_menu.title = f"Translate: {language}"
            if language in self._translate_menu:
                self._translate_menu[language].state = 1
            save_config({"translate_to": language})
        if self._general_tab:
            self._general_tab.sync(self.config)

    def _populate_devices(self):
        import contextlib

        with contextlib.suppress(AttributeError):
            self._device_menu.clear()
        current_device = self.config.get("input_device")

        default_item = rumps.MenuItem(
            "system default",
            callback=self._make_device_callback(None),
        )
        if current_device is None:
            default_item.state = 1
        self._device_menu["system default"] = default_item

        try:
            devices = list_input_devices()
        except Exception:
            devices = []

        for dev in devices:
            name = dev["name"]
            item = rumps.MenuItem(name, callback=self._make_device_callback(name))
            if current_device and current_device == name:
                item.state = 1
            self._device_menu[name] = item

        refresh_item = rumps.MenuItem(
            "Refresh", callback=lambda _: self._refresh_devices()
        )
        self._device_menu[refresh_item.title] = refresh_item

    def _refresh_devices(self):
        def do_refresh():
            self._populate_devices()

        threading.Thread(target=do_refresh, daemon=True).start()

    def _make_device_callback(self, device_name: str | None):
        def callback(_):
            self._select_device(device_name)

        return callback

    def _select_device(self, device_name: str | None):
        for key in self._device_menu:
            item = self._device_menu[key]
            if isinstance(item, rumps.MenuItem):
                item.state = 0

        self.engine.update_config({"input_device": device_name})

        label = device_name if device_name else "system default"
        check_key = label
        if check_key in self._device_menu:
            self._device_menu[check_key].state = 1

        self._device_menu.title = f"Input: {label}"
        log.info("switched input device: %s", label)
        save_config({"input_device": device_name})

    def _populate_whisper_models(self):
        current = self.config.get("whisper_model", "")
        for model_id, label in WHISPER_MODELS:
            item = rumps.MenuItem(label, callback=self._make_whisper_callback(model_id))
            if model_id == current:
                item.state = 1
            self._whisper_menu[label] = item

    def _make_whisper_callback(self, model_id: str):
        def callback(_):
            self._select_whisper_model(model_id)

        return callback

    def _select_whisper_model(self, model_id: str):
        from .preflight import is_model_cached

        for key in self._whisper_menu:
            item = self._whisper_menu[key]
            if isinstance(item, rumps.MenuItem):
                item.state = 0

        self.config["whisper_model"] = model_id
        self.engine.update_config({"whisper_model": model_id})
        save_config({"whisper_model": model_id})

        for key in self._whisper_menu:
            item = self._whisper_menu[key]
            if isinstance(item, rumps.MenuItem) and model_id in key:
                break
        else:
            item = None
        if item:
            item.state = 1

        log.info("switched whisper model: %s", model_id)

        if not is_model_cached(model_id):
            log.info("model not cached, starting download: %s", model_id)
            threading.Thread(
                target=self._download_whisper_model,
                args=(model_id,),
                daemon=True,
            ).start()

    def _download_whisper_model(self, model_id: str):
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=model_id)
            log.info("model downloaded: %s", model_id)
            if self.config.get("whisper_model") == model_id:
                self.engine._transcriber.preload()
        except Exception:
            log.exception("failed to download model: %s", model_id)

    def _toggle_postprocess(self, sender):
        new_state = not self.config.get("postprocess", True)
        self.config["postprocess"] = new_state
        self.engine.update_config({"postprocess": new_state})
        save_config({"postprocess": new_state})
        sender.state = 1 if new_state else 0
        log.info("post-processing: %s", "on" if new_state else "off")
        if self._advanced_tab:
            self._advanced_tab.sync(self.config)

    def _toggle_streaming(self, sender):
        new_state = not self.config.get("streaming", True)
        self.config["streaming"] = new_state
        self.engine.update_config({"streaming": new_state})
        save_config({"streaming": new_state})
        sender.state = 1 if new_state else 0
        log.info("streaming: %s", "on" if new_state else "off")
        if self._advanced_tab:
            self._advanced_tab.sync(self.config)

    def _toggle_theme(self, sender):
        current = self.config.get("blob_theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.config["blob_theme"] = new_theme
        save_config({"blob_theme": new_theme})
        self._overlay.set_theme(new_theme)
        sender.state = 1 if new_theme == "light" else 0
        log.info("blob theme: %s", new_theme)

    def _on_preferences(self, _):
        if self._settings_window is None:
            self._settings_window = SettingsWindow.shared(
                self.config, self._on_setting_changed
            )
            self._general_tab = GeneralTab(self.config, self._on_setting_changed)
            self._models_tab = ModelsTab(
                self.config,
                self._on_setting_changed,
                on_openai_login=self._do_openai_login,
            )
            self._audio_tab = AudioTab(self.config, self._on_setting_changed)
            self._advanced_tab = AdvancedTab(self.config, self._on_setting_changed)

            self._settings_window.set_tab_view(0, self._general_tab.view)
            self._settings_window.set_tab_view(1, self._models_tab.view)
            self._settings_window.set_tab_view(2, self._audio_tab.view)
            self._settings_window.set_tab_view(3, self._advanced_tab.view)
        else:
            self._general_tab.sync(self.config)
            self._models_tab.sync(self.config)
            self._audio_tab.sync(self.config)
            self._advanced_tab.sync(self.config)

        self._populate_settings_dynamic_data()
        self._settings_window.show()

    def _populate_settings_dynamic_data(self):
        def fetch():
            ollama_models = fetch_ollama_models(self.config["ollama_url"])
            codex_models = load_codex_models()

            try:
                devices = list_input_devices()
                device_names = [d["name"] for d in devices]
            except Exception:
                device_names = []

            token = oauth.load_token()

            def update_ui():
                if self._models_tab and ollama_models:
                    self._models_tab.refresh_ollama_models(ollama_models)
                if self._models_tab and codex_models:
                    self._models_tab.refresh_openai_models(codex_models)
                if self._audio_tab:
                    self._audio_tab.refresh_devices(device_names)
                if self._models_tab:
                    self._models_tab.update_login_status(token is not None)

            callAfter(update_ui)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_setting_changed(self, key, value):
        if key == "_refresh_devices":

            def refresh():
                try:
                    devices = list_input_devices()
                    device_names = [d["name"] for d in devices]
                except Exception:
                    device_names = []

                def update_ui():
                    if self._audio_tab:
                        self._audio_tab.refresh_devices(device_names)

                callAfter(update_ui)

            threading.Thread(target=refresh, daemon=True).start()
            return

        self.config[key] = value
        self.engine.update_config({key: value})
        save_config({key: value})

        if key == "language":
            name = next(
                (n for c, n in SPEECH_LANGUAGES if c == value),
                value,
            )
            self._speech_lang_menu.title = f"Speech: {name}"
            for k in self._speech_lang_menu:
                if isinstance(self._speech_lang_menu[k], rumps.MenuItem):
                    self._speech_lang_menu[k].state = 0
            if name in self._speech_lang_menu:
                self._speech_lang_menu[name].state = 1

        elif key == "translate_to":
            label = value if value else "Off"
            self._translate_menu.title = f"Translate: {label}"
            for k in self._translate_menu:
                if isinstance(self._translate_menu[k], rumps.MenuItem):
                    self._translate_menu[k].state = 0
            if label in self._translate_menu:
                self._translate_menu[label].state = 1

        elif key == "postprocess":
            self._postprocess_item.state = 1 if value else 0

        elif key == "streaming":
            self._streaming_item.state = 1 if value else 0

        elif key == "blob_theme":
            self._overlay.set_theme(value)
            self._theme_item.state = 1 if value == "light" else 0

        elif key == "input_device":
            label = value if value else "system default"
            self._device_menu.title = f"Input: {label}"
            for k in self._device_menu:
                item = self._device_menu[k]
                if isinstance(item, rumps.MenuItem):
                    item.state = 0
            if label in self._device_menu:
                self._device_menu[label].state = 1

        elif key == "whisper_model":
            for k in self._whisper_menu:
                item = self._whisper_menu[k]
                if isinstance(item, rumps.MenuItem):
                    item.state = 0
            for k in self._whisper_menu:
                item = self._whisper_menu[k]
                if isinstance(item, rumps.MenuItem) and value in k:
                    item.state = 1
                    break

            from .preflight import is_model_cached

            if not is_model_cached(value):
                log.info("model not cached, starting download: %s", value)
                threading.Thread(
                    target=self._download_whisper_model,
                    args=(value,),
                    daemon=True,
                ).start()

        elif key == "postprocessor":
            self._current_backend = value
            self._model_menu.title = self._model_menu_title()

        elif key == "ollama_model":
            self._current_model = value
            self._model_menu.title = self._model_menu_title()

        elif key == "openai_model":
            if self._current_backend == "openai":
                self._current_model = value
                self._model_menu.title = self._model_menu_title()

        log.info("setting changed: %s = %s", key, value)

    def _do_openai_login(self):
        def do_login():
            success = oauth.login()

            def on_done():
                self._openai_login_item.title = (
                    "Logged in" if success else "Login failed"
                )
                self._openai_login_item.set_callback(self._on_openai_login)
                if self._models_tab:
                    self._models_tab.update_login_status(success)

            callAfter(on_done)
            if success:
                threading.Thread(target=self._refresh_models, daemon=True).start()

        self._openai_login_item.title = "Logging in..."
        self._openai_login_item.set_callback(None)
        threading.Thread(target=do_login, daemon=True).start()

    def _on_openai_login(self, _):
        self._do_openai_login()

    def _on_hotkey(self):
        callAfter(lambda: self.engine.toggle())

    def _on_feedback(self):
        callAfter(self._show_feedback_pulse)
        callAfter(self._handle_feedback)

    def _show_feedback_pulse(self):
        play_sound(
            self.config.get("sound_feedback", "/System/Library/Sounds/Glass.aiff")
        )
        self._overlay.show()
        self._overlay.set_mode("pulse")

    def _handle_feedback(self):
        clipboard_text = self.clipboard._get_clipboard()
        if not clipboard_text:
            return

        result = self.engine.feedback(clipboard_text)
        if result is None:
            return

        for from_word, old_to, new_to in result.conflicts:
            response = rumps.alert(
                title="dictionary conflict",
                message=(
                    f"'{from_word}' already maps to '{old_to}'.\n"
                    f"replace with '{new_to}'?"
                ),
                ok="replace",
                cancel="keep",
            )
            if response == 1:
                self.engine._dictionary.resolve_conflict(from_word, new_to)

        if result.added:
            words = ", ".join(f"'{f}' -> '{t}'" for f, t in result.added)
            rumps.notification(
                title="dictionary updated",
                subtitle="",
                message=words,
            )

    def _on_cancel(self) -> bool:
        if self.engine.state == "idle":
            return False
        callAfter(lambda: self.engine.cancel())
        return True

    def _on_recording_started(self, event):
        callAfter(self._handle_recording_started)

    def _handle_recording_started(self):
        self._recording_source_app = focus.capture()
        self._overlay.show()
        play_sound(self.config["sound_start"])

    def _on_recording_failed(self, event):
        callAfter(self._handle_recording_failed)

    def _handle_recording_failed(self):
        self._overlay.hide()
        play_sound(self.config["sound_error"])

    def _on_recording_done(self, event):
        callAfter(self._handle_recording_done)

    def _handle_recording_done(self):
        self._overlay.set_mode("processing")
        play_sound(self.config["sound_stop"])

    def _on_transcription_failed(self, event):
        log.error("transcription failed: %s", event.error)
        callAfter(self._handle_transcription_failed)

    def _handle_transcription_failed(self):
        self._overlay.hide()
        play_sound(self.config["sound_error"])

    def _on_post_processing_done(self, event):
        callAfter(self._finish, event.raw_text, event.processed_text)

    def _on_post_processing_failed(self, event):
        callAfter(self._finish, event.raw_text, event.raw_text)

    def _on_cancelled(self, event):
        callAfter(self._handle_cancelled)

    def _handle_cancelled(self):
        self._overlay.hide()
        play_sound(self.config["sound_cancel"])

    def _finish(self, raw_text, processed_text):
        self._overlay.hide()
        focus.restore(self._recording_source_app)
        self.clipboard.paste(processed_text)
        save_to_history(raw_text, processed_text)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    from .preflight import run_checks

    config = load_config()
    if not run_checks(config):
        sys.exit(1)

    app = LocalWhisperApp()
    app.run()


if __name__ == "__main__":
    main()
