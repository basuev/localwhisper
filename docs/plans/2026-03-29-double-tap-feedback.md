# Double-tap visual feedback implementation plan

**Spec:** `docs/specs/2026-03-29-double-tap-feedback.md`
**Date:** 2026-03-29

## Goal

Add visual (pulse blob) and audio (Glass.aiff) feedback when user double-taps Option key.

## File structure

- Modify: `localwhisper/config.py` - add `sound_feedback` default
- Modify: `localwhisper/overlay.py` - add "pulse" mode to AudioOverlay
- Modify: `localwhisper/app.py` - play sound + show pulse in `_on_feedback`
- Modify: `tests/test_config.py` - add `sound_feedback` to required keys
- Create: `tests/test_overlay.py` - pulse mode tests

## Tasks

### Task 1: Add `sound_feedback` config key

**Files:**
- Modify: `localwhisper/config.py`
- Modify: `tests/test_config.py`

**Dependencies:** None

**Steps:**

- [ ] Step 1: Add `sound_feedback` to REQUIRED_CONFIG_KEYS in test

  In `tests/test_config.py`, add `"sound_feedback"` to the `REQUIRED_CONFIG_KEYS` list:

  ```python
  REQUIRED_CONFIG_KEYS = [
      ...
      "sound_cancel",
      "sound_feedback",
      "postprocess",
      ...
  ]
  ```

- [ ] Step 2: Run test, verify it fails

  Run: `uv run pytest tests/test_config.py::test_default_config_has_all_keys -x`
  Expected: FAIL with "missing config keys: ['sound_feedback']"

- [ ] Step 3: Add `sound_feedback` to DEFAULT_CONFIG

  In `localwhisper/config.py`, add after `sound_error` line:

  ```python
  "sound_feedback": "/System/Library/Sounds/Glass.aiff",
  ```

- [ ] Step 4: Run test, verify it passes

  Run: `uv run pytest tests/test_config.py -x`
  Expected: PASS

- [ ] Step 5: Commit

  `feat: add sound_feedback config key with Glass.aiff default`

**Verification:**
- `uv run pytest tests/test_config.py -x` passes

### Task 2: Add "pulse" mode to AudioOverlay

**Files:**
- Create: `tests/test_overlay.py`
- Modify: `localwhisper/overlay.py`

**Dependencies:** None

**Steps:**

- [ ] Step 1: Write failing tests for pulse mode

  Create `tests/test_overlay.py`:

  ```python
  import math
  from unittest.mock import MagicMock, patch

  import pytest


  @pytest.fixture
  def overlay():
      with patch("localwhisper.overlay.AppKit"), \
           patch("localwhisper.overlay.Quartz"):
          from localwhisper.overlay import AudioOverlay

          ov = AudioOverlay.__new__(AudioOverlay)
          ov._panel = None
          ov._blob_view = None
          ov._timer = None
          ov._amplitude = 0.0
          ov._lock = __import__("threading").Lock()
          ov._start_time = 0.0
          ov._theme = "dark"
          ov._mode = "recording"
          ov._pulse_start = None
          return ov


  def test_set_mode_pulse_stores_mode(overlay):
      overlay._blob_view = MagicMock()
      overlay._timer = MagicMock()
      with patch("localwhisper.overlay.AppKit"):
          overlay.set_mode("pulse")
      assert overlay._mode == "pulse"


  def test_pulse_tick_amplitude_follows_sine(overlay):
      from localwhisper.overlay import PULSE_DURATION

      overlay._mode = "pulse"
      overlay._pulse_start = 0.0
      overlay._blob_view = MagicMock()

      t = PULSE_DURATION / 2
      overlay._start_time = -t
      overlay._pulse_start = -t

      with patch("localwhisper.overlay.time") as mock_time:
          mock_time.monotonic.return_value = 0.0
          overlay._tick()

      call_args = overlay._blob_view.setAmplitude_.call_args[0][0]
      expected = math.sin(math.pi * 0.5)
      assert abs(call_args - expected) < 0.01


  def test_pulse_auto_hides_after_duration(overlay):
      from localwhisper.overlay import PULSE_DURATION

      overlay._mode = "pulse"
      overlay._blob_view = MagicMock()
      overlay._panel = MagicMock()
      overlay._timer = MagicMock()

      overlay._pulse_start = 0.0
      overlay._start_time = 0.0

      with patch("localwhisper.overlay.time") as mock_time:
          mock_time.monotonic.return_value = PULSE_DURATION + 0.01
          overlay._tick()

      overlay._panel.orderOut_.assert_called_once()


  def test_pulse_does_not_use_shimmer(overlay):
      overlay._blob_view = MagicMock()
      overlay._timer = MagicMock()
      with patch("localwhisper.overlay.AppKit"):
          overlay.set_mode("pulse")
      overlay._blob_view.setShimmer_.assert_called_with(False)
  ```

- [ ] Step 2: Run tests, verify they fail

  Run: `uv run pytest tests/test_overlay.py -x`
  Expected: FAIL (PULSE_DURATION not defined, _pulse_start not an attribute, etc.)

- [ ] Step 3: Implement pulse mode in AudioOverlay

  In `localwhisper/overlay.py`:

  Add constant after MAX_RADIUS:
  ```python
  PULSE_DURATION = 0.5
  ```

  Add `_pulse_start` to `__init__`:
  ```python
  self._pulse_start = None
  ```

  Update `set_mode` to handle "pulse":
  ```python
  def set_mode(self, mode):
      self._mode = mode
      if self._blob_view is not None:
          self._blob_view.setShimmer_(mode == "processing")
      if mode == "pulse":
          self._pulse_start = time.monotonic()
      if self._timer is not None:
          self._timer.invalidate()
          fps = 30.0 if mode == "processing" else 60.0
          self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
              1.0 / fps,
              True,
              lambda _: self._tick(),
          )
  ```

  Update `show` to reset `_pulse_start`:
  ```python
  self._pulse_start = None
  ```
  (add after the existing `self._mode = "recording"` line)

  Update `_tick` to handle pulse mode:
  ```python
  def _tick(self):
      try:
          t = time.monotonic() - self._start_time
          if self._mode == "pulse":
              elapsed = time.monotonic() - self._pulse_start
              if elapsed >= PULSE_DURATION:
                  self.hide()
                  return
              progress = elapsed / PULSE_DURATION
              amp = math.sin(math.pi * progress)
          elif self._mode == "processing":
              amp = 0.15 + 0.10 * math.sin(t * 1.8)
          else:
              with self._lock:
                  amp = self._amplitude
          self._blob_view.setAmplitude_(amp)
          self._blob_view.setTime_(t)
          self._blob_view.setNeedsDisplay_(True)
      except Exception:
          log.exception("overlay tick failed")
  ```

- [ ] Step 4: Run tests, verify they pass

  Run: `uv run pytest tests/test_overlay.py -x`
  Expected: PASS

- [ ] Step 5: Commit

  `feat: add pulse mode to AudioOverlay with auto-hide`

**Verification:**
- `uv run pytest tests/test_overlay.py -x` passes

### Task 3: Wire feedback sound and pulse in app

**Files:**
- Modify: `localwhisper/app.py`

**Dependencies:** Task 1 (sound_feedback config key), Task 2 (pulse mode)

**Steps:**

- [ ] Step 1: Update `_on_feedback` to play sound and show pulse

  In `localwhisper/app.py`, replace:

  ```python
  def _on_feedback(self):
      callAfter(self._handle_feedback)
  ```

  with:

  ```python
  def _on_feedback(self):
      callAfter(self._show_feedback_pulse)
      callAfter(self._handle_feedback)

  def _show_feedback_pulse(self):
      play_sound(self.config.get("sound_feedback", "/System/Library/Sounds/Glass.aiff"))
      self._overlay.set_mode("pulse")
      self._overlay.show()
  ```

- [ ] Step 2: Run full verify

  Run: `bash scripts/verify.sh`
  Expected: PASS

- [ ] Step 3: Commit

  `feat: play sound and show pulse on double-tap feedback`

**Verification:**
- `bash scripts/verify.sh` passes

## Final verification

- [ ] All tests pass: `bash scripts/verify.sh`
- [ ] Linter clean: `uv run ruff check localwhisper/ tests/`
- [ ] Manual test: double-tap Right Option after a transcription - should hear Glass sound and see blob pulse
