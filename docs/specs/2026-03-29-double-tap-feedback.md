# Double-tap visual feedback specification

**Date:** 2026-03-29
**Status:** Approved

## Goal

Add visual and audio feedback when user double-taps Option key to trigger dictionary correction.

## Architecture

Extends existing overlay and sound systems. No new modules - changes in overlay.py, config.py, app.py.

## Components

### 1. AudioOverlay - new "pulse" mode

- One sinusoidal expansion-contraction cycle over 0.5s
- Radius: base (28px) -> max (65px) -> base
- 60 FPS refresh rate (same as recording mode)
- Auto-hides when cycle completes (calls `hide()` internally)
- `set_mode("pulse")` sets mode, `show()` starts animation

### 2. Config - new key `sound_feedback`

- Default: `/System/Library/Sounds/Glass.aiff`
- Added to `DEFAULT_CONFIG` alongside existing sound keys

### 3. App feedback handler update

- `_on_feedback()`: play `sound_feedback` sound, show pulse overlay
- Existing `_handle_feedback()` logic unchanged

## Data flow

```
Double-tap detected (HotkeyListener)
  -> _on_feedback() [event tap thread]
     -> play sound_feedback
     -> overlay.set_mode("pulse") + overlay.show() [via callAfter]
     -> callAfter(_handle_feedback)

Pulse animation (0.5s, main thread):
  -> sin-based radius cycle
  -> auto-hide() on completion

_handle_feedback (main thread, existing):
  -> clipboard read
  -> engine.feedback()
  -> conflict alerts if needed
  -> notification with result
```

## Error handling

- If overlay is already visible (e.g. recording in progress) - pulse should not interfere. Double-tap during recording/processing is already blocked by engine state check.
- Missing sound file - existing sound playback code handles this gracefully (no crash).

## Testing strategy

- Unit test: pulse mode timing - verify auto-hide called after cycle
- Unit test: config key `sound_feedback` has correct default
- Unit test: `_on_feedback` triggers sound and overlay

## Open questions

None.
