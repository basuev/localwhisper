# localwhisper

macOS status bar app for local speech-to-text using MLX Whisper on Apple Silicon, with Ollama or OpenAI post-processing.

## features

- local transcription with MLX Whisper
- menu bar UI with global hotkey recording
- automatic paste back into the previously focused app
- optional post-processing via Ollama or OpenAI
- optional translation
- launch via Spotlight after Homebrew Cask install
- launch at login toggle in Preferences

## requirements

- macOS on Apple Silicon
- Homebrew for app install
- Ollama for local post-processing

## installation

```bash
brew install basuev/localwhisper/localwhisper
```

After installation:

1. launch `localwhisper` via Spotlight
2. allow Microphone access when macOS asks
3. allow Accessibility access for `localwhisper`
4. wait for the first Whisper model download to finish on first launch

## usage

1. focus the app where you want text inserted
2. press `Right Option` to start recording
3. press `Right Option` again to stop recording
4. wait for transcription and optional post-processing
5. the result is pasted back into the previously focused app

Press `Escape` during recording to cancel.

## configuration

Config file: `~/.config/localwhisper/config.yaml`

Important settings:

| option | default | description |
|--------|---------|-------------|
| `whisper_model` | `mlx-community/whisper-large-v3-mlx` | Whisper model |
| `language` | `ru` | speech language |
| `ollama_model` | `gemma3:4b` | Ollama model |
| `postprocessor` | `ollama` | `ollama` or `openai` |
| `launch_at_login` | `true` | start app automatically after login |
| `hotkey_keycode` | `61` | hotkey, `61` is Right Option |
| `translate_to` | `null` | translation target or disabled |
| `input_device` | `null` | audio input device or system default |

See [config.example.yaml](config.example.yaml) for the full config.

## file locations

| purpose | path |
|---------|------|
| app | `/Applications/localwhisper.app` |
| config | `~/.config/localwhisper/config.yaml` |
| auth | `~/.config/localwhisper/auth.json` |
| history | `~/.local/share/localwhisper/history.jsonl` |
| logs | `~/.local/share/localwhisper/app.log` |

## development

Install dependencies:

```bash
uv sync --group dev --group packaging
```

Run from source:

```bash
./scripts/run.sh
```

Verify:

```bash
bash scripts/verify.sh
```

Build the macOS app bundle:

```bash
bash scripts/build_app.sh
```

This produces:

- `dist/localwhisper.app`
- `dist/localwhisper.app.zip`
- `dist/localwhisper.rb` after running `scripts/render_cask.py`
