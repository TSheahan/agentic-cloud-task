#!/usr/bin/env python3
"""Generate synthetic "hey Sara" WAV samples using the forked_assistant TTS backends.

Runs on the Pi (or any machine with API keys). Produces 16 kHz mono S16_LE WAV
files suitable for OpenWakeWord training after resampling.

Usage:
    cd ~/raspberry-ai/mvp-modules/forked_assistant
    source ~/venv/bin/activate
    python ~/sara/hudsons-bay/generate_samples.py --backend cartesia --count 5
    python ~/sara/hudsons-bay/generate_samples.py --backend elevenlabs --count 5
"""

import argparse
import sys
import time
from pathlib import Path

# Add forked_assistant/src to path so we can import tts module
_SRC = Path(__file__).resolve().parents[1] / ".." / "raspberry-ai" / "mvp-modules" / "forked_assistant" / "src"
if not _SRC.exists():
    _SRC = Path.home() / "raspberry-ai" / "mvp-modules" / "forked_assistant" / "src"
sys.path.insert(0, str(_SRC))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv(usecwd=True), override=True)
load_dotenv(Path.home() / ".env", override=True)

from loguru import logger
from tts import CartesiaTTS, ElevenLabsTTS, DeepgramTTS

PHRASE = "hey Sara"
OUTPUT_DIR = Path(__file__).resolve().parent / "samples"

BACKENDS = {
    "cartesia": CartesiaTTS,
    "elevenlabs": ElevenLabsTTS,
    "deepgram": DeepgramTTS,
}


def main():
    p = argparse.ArgumentParser(description=f"Generate synthetic '{PHRASE}' WAV samples")
    p.add_argument("--backend", "-b", choices=list(BACKENDS), default="cartesia")
    p.add_argument("--count", "-n", type=int, default=5, help="Number of samples to generate")
    p.add_argument("--out-dir", "-o", type=str, default=None, help="Output directory (default: ./samples)")
    args = p.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else OUTPUT_DIR / args.backend
    out_dir.mkdir(parents=True, exist_ok=True)

    tts = BACKENDS[args.backend]()
    tts.warm()

    for i in range(args.count):
        fname = f"hey_sara_{args.backend}_{i:04d}.wav"
        path = out_dir / fname
        t0 = time.monotonic()
        tts.synthesise_to_file(PHRASE, path)
        elapsed = (time.monotonic() - t0) * 1000
        size = path.stat().st_size if path.exists() else 0
        logger.info("[{}/{}] {} ({} bytes, {:.0f}ms)", i + 1, args.count, fname, size, elapsed)

    tts.close()
    logger.info("done — {} samples in {}", args.count, out_dir)


if __name__ == "__main__":
    main()
