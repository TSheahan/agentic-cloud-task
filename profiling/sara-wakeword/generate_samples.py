#!/usr/bin/env python3
"""Generate synthetic WAV samples using the forked_assistant TTS backends.

Happy path for OWW training: **Cartesia** (`--backend cartesia`, default) on a
machine with API keys. Use `--phrases-file` (one phrase per line) for adversarial
negatives aligned with `hey_sara_model.yml` / domain-knowledge.md.

Produces 16 kHz mono S16_LE WAV files suitable for OpenWakeWord after rsync to
`hey_sara_output/<model_name>/{positive_train,positive_test,negative_train,negative_test}/`.

Usage:
    python profiling/sara-wakeword/generate_samples.py --backend cartesia --count 100 -o ./out/pos
    python profiling/sara-wakeword/generate_samples.py -b cartesia --phrases-file negatives.txt --count 50 -o ./out/neg
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
    p = argparse.ArgumentParser(
        description="Generate synthetic WAV samples (default backend: cartesia)"
    )
    p.add_argument("--backend", "-b", choices=list(BACKENDS), default="cartesia")
    p.add_argument(
        "--phrase",
        type=str,
        default=None,
        help=f"Single phrase to synthesize (default: {PHRASE!r})",
    )
    p.add_argument(
        "--phrases-file",
        type=str,
        default=None,
        help="Text file, one phrase per line; --count samples per phrase",
    )
    p.add_argument(
        "--count",
        "-n",
        type=int,
        default=5,
        help="Samples per phrase (single phrase or each line of --phrases-file)",
    )
    p.add_argument(
        "--out-dir",
        "-o",
        type=str,
        default=None,
        help="Output directory (default: ./samples/<backend>)",
    )
    args = p.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else OUTPUT_DIR / args.backend
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.phrases_file:
        lines = [
            ln.strip()
            for ln in Path(args.phrases_file).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        phrases = lines
    else:
        phrases = [args.phrase or PHRASE]

    tts = BACKENDS[args.backend]()
    tts.warm()

    n_total = 0
    for pi, phrase in enumerate(phrases):
        for i in range(args.count):
            fname = f"p{pi:03d}_{args.backend}_{i:04d}.wav"
            path = out_dir / fname
            t0 = time.monotonic()
            tts.synthesise_to_file(phrase, path)
            elapsed = (time.monotonic() - t0) * 1000
            size = path.stat().st_size if path.exists() else 0
            n_total += 1
            logger.info(
                "[{}] {} ({!r}, {} bytes, {:.0f}ms)",
                n_total,
                fname,
                phrase[:48] + ("…" if len(phrase) > 48 else ""),
                size,
                elapsed,
            )

    tts.close()
    logger.info("done — {} samples in {}", n_total, out_dir)


if __name__ == "__main__":
    main()
