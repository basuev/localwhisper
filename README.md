# LocalWhisper

macOS status bar app for local speech-to-text using MLX Whisper on Apple Silicon, with LLM post-processing via Ollama or OpenAI.

## Features

- **Local transcription** - MLX Whisper optimized for Apple Silicon, no cloud dependency
- **Hotkey recording** - press Right Option to toggle recording on/off
- **LLM post-processing** - grammar correction and formatting via Ollama (local) or OpenAI ChatGPT
- **Auto-paste** - result is pasted into the app you were using before recording
- **Translation** - optional translation to any target language
- **10 languages** - Russian, English, German, French, Spanish, Japanese, Chinese, Korean, Ukrainian, Polish
- **Status bar UI** - visual recording/processing indicators, menu-based configuration
- **Sound feedback** - audio cues for recording start, stop, cancel, and errors
- **Model management** - auto-unload after idle timeout, runtime model switching
- **History** - all transcriptions saved to JSONL with timestamps

## Requirements

- macOS on Apple Silicon (M1+)
- Python 3.11 - 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.ai/) (for local post-processing)

## Installation

```bash
bash scripts/install.sh
```

This will:

1. Install and start Ollama, pull the default LLM model
2. Set up the Python environment via `uv sync`
3. Download the Whisper model (~3 GB)
4. Create config at `~/.config/localwhisper/config.yaml`
5. Install a launchd service for auto-start at login

After installation, grant Accessibility permission:

**System Settings -> Privacy & Security -> Accessibility** - add your terminal app.

## Usage

Start the app:

```bash
# Via launchd (installed by install.sh)
launchctl load ~/Library/LaunchAgents/com.localwhisper.agent.plist

# Or run directly
.venv/bin/localwhisper
```

### Workflow

1. Focus the app where you want text inserted
2. Press **Right Option** - recording starts (sound cue + red status icon)
3. Press **Right Option** again - recording stops, transcription and post-processing run
4. Result is automatically pasted into the original app

Press **Escape** during recording to cancel.

### Status bar menu

- Switch post-processor backend (Ollama / OpenAI)
- Change Ollama or OpenAI model
- Toggle translation and select target language
- Change speech language
- OpenAI login/logout

## Configuration

Config file: `~/.config/localwhisper/config.yaml`

See [config.example.yaml](config.example.yaml) for all options. Key settings:

| Option | Default | Description |
|--------|---------|-------------|
| `whisper_model` | `mlx-community/whisper-large-v3-mlx` | MLX Whisper model |
| `language` | `ru` | Speech language |
| `ollama_model` | `qwen2.5:7b` | Ollama LLM model |
| `postprocessor` | `ollama` | Backend: `ollama` or `openai` |
| `hotkey_keycode` | `61` | Hotkey (61 = Right Option) |
| `model_idle_timeout` | `300` | Seconds before unloading model |
| `recording_volume` | `100` | Mic volume during recording (0-100) |
| `translate_to` | `null` | Target language or null to disable |
| `input_device` | `null` | Audio input device (null = default) |

## File locations

| Purpose | Path |
|---------|------|
| Config | `~/.config/localwhisper/config.yaml` |
| History | `~/.local/share/localwhisper/history.jsonl` |
| Logs | `~/.local/share/localwhisper/stdout.log`, `stderr.log` |
| launchd | `~/Library/LaunchAgents/com.localwhisper.agent.plist` |

## Development

Install dev dependencies:

```bash
uv sync --group dev
```

Run tests:

```bash
bash scripts/verify.sh
```

Full verification (includes Whisper model download):

```bash
bash scripts/verify.sh --full
```

### Test layers

| Layer | File | What it checks | Time |
|-------|------|----------------|------|
| 0 | `tests/test_quick.py` | Imports, config, entry point | < 5s |
| 1 | `tests/test_unit.py` | Config merging, history, WAV encoding | < 10s |
| 2 | `tests/test_integration.py` | Ollama, clipboard, sounds, transcriber | < 2 min |
