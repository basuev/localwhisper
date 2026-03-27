# localwhisper

macOS status bar app for local speech-to-text using MLX Whisper on Apple Silicon, with LLM post-processing via Ollama or OpenAI.

## features

- **local transcription** - MLX Whisper optimized for Apple Silicon, no cloud dependency
- **hotkey recording** - press Right Option to toggle recording on/off
- **LLM post-processing** - grammar correction and formatting via Ollama (local) or OpenAI ChatGPT
- **auto-paste** - result is pasted into the app you were using before recording
- **translation** - optional translation to any target language
- **10 languages** - Russian, English, German, French, Spanish, Japanese, Chinese, Korean, Ukrainian, Polish
- **status bar UI** - visual recording/processing indicators, menu-based configuration
- **sound feedback** - audio cues for recording start, stop, cancel, and errors
- **model management** - auto-unload after idle timeout, runtime model switching
- **history** - all transcriptions saved to JSONL with timestamps

## requirements

- macOS on Apple Silicon (M1+)
- Python 3.11 - 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.ai/) (for local post-processing)

## installation

```bash
bash scripts/install.sh
```

this will:

1. install and start Ollama, pull the default LLM model
2. set up the Python environment via `uv sync`
3. download the Whisper model (~3 GB)
4. create config at `~/.config/localwhisper/config.yaml`
5. install a launchd service for auto-start at login

after installation, grant Accessibility permission:

**System Settings -> Privacy & Security -> Accessibility** - add your terminal app.

## usage

start the app:

```bash
# via launchd (installed by install.sh)
launchctl load ~/Library/LaunchAgents/com.localwhisper.agent.plist

# or run directly
.venv/bin/localwhisper
```

### workflow

1. focus the app where you want text inserted
2. press **Right Option** - recording starts (sound cue + red status icon)
3. press **Right Option** again - recording stops, transcription and post-processing run
4. result is automatically pasted into the original app

press **Escape** during recording to cancel.

### status bar menu

- switch post-processor backend (Ollama / OpenAI)
- change Ollama or OpenAI model
- toggle translation and select target language
- change speech language
- OpenAI login/logout

## configuration

config file: `~/.config/localwhisper/config.yaml`

see [config.example.yaml](config.example.yaml) for all options. key settings:

| option | default | description |
|--------|---------|-------------|
| `whisper_model` | `mlx-community/whisper-large-v3-mlx` | MLX Whisper model |
| `language` | `ru` | speech language |
| `ollama_model` | `gemma3:4b` | Ollama LLM model |
| `postprocessor` | `ollama` | backend: `ollama` or `openai` |
| `hotkey_keycode` | `61` | hotkey (61 = Right Option) |
| `model_idle_timeout` | `300` | seconds before unloading model |
| `recording_volume` | `100` | mic volume during recording (0-100) |
| `translate_to` | `null` | target language or null to disable |
| `input_device` | `null` | audio input device (null = default) |

## file locations

| purpose | path |
|---------|------|
| config | `~/.config/localwhisper/config.yaml` |
| history | `~/.local/share/localwhisper/history.jsonl` |
| logs | `~/.local/share/localwhisper/stdout.log`, `stderr.log` |
| launchd | `~/Library/LaunchAgents/com.localwhisper.agent.plist` |

## development

install dev dependencies:

```bash
uv sync --group dev
```

run tests:

```bash
bash scripts/verify.sh
```

full verification (includes Whisper model download):

```bash
bash scripts/verify.sh --full
```

### test layers

| layer | file | what it checks | time |
|-------|------|----------------|------|
| 0 | `tests/test_quick.py` | imports, config, entry point | < 5s |
| 1 | `tests/test_unit.py` | config merging, history, WAV encoding | < 10s |
| 2 | `tests/test_integration.py` | Ollama, clipboard, sounds, transcriber | < 2 min |
