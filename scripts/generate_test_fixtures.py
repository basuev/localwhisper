#!/usr/bin/env python3
"""Generate test fixture files."""

from pathlib import Path

import numpy as np
import soundfile as sf

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1 second of silence at 16kHz
    silence = np.zeros(16000, dtype=np.float32)
    wav_path = FIXTURES_DIR / "silence_1s.wav"
    sf.write(str(wav_path), silence, 16000, subtype="FLOAT")
    print(f"Created {wav_path}")


if __name__ == "__main__":
    main()
